from __future__ import annotations

import hmac
import html
import json
import os
import secrets
import smtplib
import ssl
import string
import threading
import time
import uuid
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, Response, jsonify, request, send_from_directory

from .db import BACKUP_VERSION, backup_database, connect, export_payload, init_db, validate_backup

APP_VERSION = "6.0.0"
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "app.sqlite"
BACKUPS_DIR = DATA_DIR / "backups"
BACKUP_KEEP = max(1, int(os.getenv("BACKUP_KEEP", "50")))
APP_TITLE = os.getenv("APP_TITLE", "Chez Philipp")
APP_URL = os.getenv("APP_URL", "").rstrip("/")
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Zurich")
PWA_ALLOWED_ORIGIN = os.getenv("PWA_ALLOWED_ORIGIN", "").rstrip("/")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
ADMIN_PIN = os.getenv("ADMIN_PIN", "")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))

NOTIFY_ENABLED = os.getenv("NOTIFY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = max(1, min(65535, int(os.getenv("SMTP_PORT", "465"))))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "ssl").strip().lower()
SMTP_TIMEOUT = max(3, min(60, int(os.getenv("SMTP_TIMEOUT", "12"))))
NOTIFY_RETRY_SECONDS = max(15, int(os.getenv("NOTIFY_RETRY_SECONDS", "60")))
NOTIFY_MAX_ATTEMPTS = max(1, min(100, int(os.getenv("NOTIFY_MAX_ATTEMPTS", "12"))))
BOOKING_CUSTOMER_NAME = (os.getenv("BOOKING_CUSTOMER_NAME", "Meine Frau").strip() or "Meine Frau")[:120]
CALENDAR_FEED_TOKEN = os.getenv("CALENDAR_FEED_TOKEN", "").strip()

try:
    TZ = ZoneInfo(APP_TIMEZONE)
except Exception:
    TZ = ZoneInfo("UTC")

init_db(DB_PATH, BACKUPS_DIR, BACKUP_KEEP)
app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = SECRET_KEY

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self' https:",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
])

_notification_lock = threading.Lock()
_worker_started = False


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def utc_iso(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


def json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def admin_allowed() -> bool:
    if not AUTH_ENABLED:
        return True
    supplied = request.headers.get("X-Admin-Pin", "")
    return bool(ADMIN_PIN) and hmac.compare_digest(supplied, ADMIN_PIN)


def require_admin():
    if admin_allowed():
        return None
    return json_error("Admin-Anmeldung erforderlich", 401)


def parse_minutes(value: str) -> int:
    hh, mm = value.split(":")
    return int(hh) * 60 + int(mm)


def minutes_to_time(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def valid_date(value: str) -> date_cls:
    return datetime.strptime(value, "%Y-%m-%d").date()


def generate_code(conn) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "CP-" + "".join(secrets.choice(alphabet) for _ in range(8))
        if not conn.execute("SELECT 1 FROM bookings WHERE public_code=?", (code,)).fetchone():
            return code


def availability_windows(conn, booking_date: str) -> tuple[list[tuple[int, int]], int]:
    """Return availability windows and slot interval. Date overrides replace the weekly rule."""
    day = valid_date(booking_date)
    overrides = conn.execute(
        "SELECT * FROM availability_overrides WHERE date=? ORDER BY start_time", (booking_date,)
    ).fetchall()
    if overrides:
        if any(row["kind"] == "closed" for row in overrides):
            return [], 30
        windows = []
        for row in overrides:
            if row["kind"] != "available":
                continue
            start, end = parse_minutes(row["start_time"]), parse_minutes(row["end_time"])
            if start < end:
                windows.append((start, end))
        hours = conn.execute("SELECT slot_interval_min FROM opening_hours WHERE weekday=?", (day.weekday(),)).fetchone()
        return windows, int(hours["slot_interval_min"]) if hours else 30

    hours = conn.execute("SELECT * FROM opening_hours WHERE weekday=?", (day.weekday(),)).fetchone()
    if not hours or not hours["enabled"]:
        return [], 30
    return [(parse_minutes(hours["start_time"]), parse_minutes(hours["end_time"]))], int(hours["slot_interval_min"])


def has_confirmed_conflict(conn, booking_date: str, start_time: str, end_time: str, exclude_id: str = "") -> bool:
    start, end = parse_minutes(start_time), parse_minutes(end_time)
    rows = conn.execute(
        "SELECT id,start_time,end_time FROM bookings WHERE date=? AND status='confirmed'", (booking_date,)
    ).fetchall()
    return any(row["id"] != exclude_id and start < parse_minutes(row["end_time"]) and end > parse_minutes(row["start_time"]) for row in rows)


def availability(conn, booking_date: str, service_id: str) -> list[str]:
    day = valid_date(booking_date)
    service = conn.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
    if not service:
        raise ValueError("Leistung nicht gefunden")
    windows, step = availability_windows(conn, booking_date)
    duration = int(service["duration_min"])
    current = datetime.now(TZ)
    slots = []
    for start, end in windows:
        cursor = start
        while cursor + duration <= end:
            slot_end = cursor + duration
            overlaps = has_confirmed_conflict(conn, booking_date, minutes_to_time(cursor), minutes_to_time(slot_end))
            in_past = day == current.date() and cursor <= current.hour * 60 + current.minute
            if not overlaps and not in_past and day >= current.date():
                slots.append(minutes_to_time(cursor))
            cursor += max(5, step)
    return sorted(set(slots))


def notification_configured() -> bool:
    return bool(NOTIFY_ENABLED and NOTIFY_EMAIL and SMTP_HOST and SMTP_FROM)


def _display_date(value: str) -> str:
    day = valid_date(value)
    weekdays = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
    months = ("", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember")
    return f"{weekdays[day.weekday()]}, {day.day}. {months[day.month]} {day.year}"


def _mail_body(booking: dict) -> str:
    requested = (booking.get("notification_type") == "new_request" or booking.get("status") == "requested")
    lines = [
        "Neue Terminanfrage bei Chez Philipp" if requested else "Neue Buchung bei Chez Philipp",
        "",
        f"Termin: {_display_date(booking['date'])}",
        f"Zeit: {booking['start_time']}–{booking['end_time']} Uhr",
        f"Behandlung: {booking['service_name']}",
    ]
    if booking.get("nail_color_name"):
        lines.append(f"Farbe: {booking['nail_color_name']}")
    lines.append(f"Buchungscode: {booking['public_code']}")
    if booking.get("notes"):
        lines.extend(["", f"Notiz: {booking['notes']}"])
    if requested:
        lines.extend(["", "Diese Uhrzeit wurde frei angefragt und ist noch nicht bestätigt.", "Die Wunschzeit ist als vorläufige Kalenderdatei (.ics) angehängt."])
    else:
        lines.extend(["", "Der Termin ist als Kalenderdatei (.ics) angehängt."])
    return "\n".join(lines)


def _mail_html(booking: dict) -> str:
    esc = lambda value: html.escape(str(value or ""), quote=True)
    color_row = ""
    if booking.get("nail_color_name"):
        hex_value = str(booking.get("nail_color_hex") or "").strip()
        dot = ""
        if len(hex_value) == 7 and hex_value.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in hex_value[1:]):
            dot = f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{hex_value};border:1px solid #d6cec4;vertical-align:-1px;margin-right:7px"></span>'
        color_row = f'<tr><td style="padding:7px 0;color:#746b61;width:110px">Farbe</td><td style="padding:7px 0;font-weight:600;color:#211d19">{dot}{esc(booking["nail_color_name"])}</td></tr>'
    notes = ""
    if booking.get("notes"):
        notes = f'<div style="margin-top:18px;padding:14px 16px;background:#f7f3ed;border-radius:12px;color:#3f3933"><div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#8c8176;margin-bottom:6px">Notiz</div>{esc(booking["notes"])}</div>'
    return f'''<!doctype html>
<html><body style="margin:0;padding:0;background:#f3efe9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#211d19">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3efe9;padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#fffdf9;border:1px solid #e7ded3;border-radius:20px;overflow:hidden">
<tr><td style="padding:28px 28px 20px;background:#25211d;color:#fffdf9">
<div style="font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#d9c9b8">Chez Philipp</div>
<div style="font-family:Georgia,'Times New Roman',serif;font-size:28px;line-height:1.2;margin-top:8px">{"Neue Terminanfrage" if (booking.get("notification_type") == "new_request" or booking.get("status") == "requested") else "Neue Buchung"}</div>
</td></tr>
<tr><td style="padding:26px 28px 30px">
<div style="font-family:Georgia,'Times New Roman',serif;font-size:22px;line-height:1.35;margin-bottom:18px">{esc(_display_date(booking['date']))}<br><span style="color:#806b57">{esc(booking['start_time'])}–{esc(booking['end_time'])} Uhr</span></div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="font-size:15px;border-top:1px solid #eee6dc;border-bottom:1px solid #eee6dc;padding:8px 0">
<tr><td style="padding:7px 0;color:#746b61;width:110px">Behandlung</td><td style="padding:7px 0;font-weight:600;color:#211d19">{esc(booking['service_name'])}</td></tr>
{color_row}
<tr><td style="padding:7px 0;color:#746b61">Buchungscode</td><td style="padding:7px 0;font-weight:600;color:#211d19">{esc(booking['public_code'])}</td></tr>
</table>
{notes}
<div style="margin-top:20px;font-size:13px;line-height:1.5;color:#746b61">{"Diese Uhrzeit wurde frei angefragt und ist noch nicht bestätigt. Die angehängte <strong>.ics-Datei</strong> ist deshalb als vorläufiger Termin gekennzeichnet." if (booking.get("notification_type") == "new_request" or booking.get("status") == "requested") else "Der Termin ist als <strong>.ics-Datei</strong> angehängt und kann direkt in den Kalender übernommen werden."}</div>
</td></tr></table>
</td></tr></table>
</body></html>'''


def _ics_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _booking_event_lines(booking: dict, force_confirmed: bool = False) -> list[str]:
    local_start = datetime.strptime(f"{booking['date']} {booking['start_time']}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    local_end = datetime.strptime(f"{booking['date']} {booking['end_time']}", "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    if local_end <= local_start:
        local_end += timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    end_utc = local_end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    updated_raw = booking.get("updated_at") or booking.get("created_at")
    try:
        updated = datetime.fromisoformat(str(updated_raw)).astimezone(timezone.utc) if updated_raw else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        updated = datetime.now(timezone.utc)
    stamp = updated.strftime("%Y%m%dT%H%M%SZ")
    requested = not force_confirmed and (booking.get("notification_type") == "new_request" or booking.get("status") == "requested")
    description = f"Buchungscode: {booking['public_code']}"
    if requested:
        description += "\nStatus: Terminanfrage – noch nicht bestätigt"
    if booking.get("nail_color_name"):
        description += f"\nFarbe: {booking['nail_color_name']}"
    if booking.get("notes"):
        description += f"\nNotiz: {booking['notes']}"
    uid_base = str(booking.get("id") or booking["public_code"]).replace("@", "-")
    summary = ("Chez Philipp · Anfrage · " if requested else "Chez Philipp · ") + booking["service_name"]
    return [
        "BEGIN:VEVENT",
        f"UID:{_ics_escape(uid_base)}@chez-philipp.local",
        f"DTSTAMP:{stamp}",
        f"LAST-MODIFIED:{stamp}",
        f"DTSTART:{start_utc}",
        f"DTEND:{end_utc}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        "STATUS:TENTATIVE" if requested else "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT" if requested else "TRANSP:OPAQUE",
        "END:VEVENT",
    ]


def _booking_ics(booking: dict) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chez Philipp//Booking//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        *_booking_event_lines(booking),
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")


def _calendar_feed_ics(bookings: list[dict]) -> bytes:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chez Philipp//Calendar Feed//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Chez Philipp",
        f"X-WR-TIMEZONE:{_ics_escape(APP_TIMEZONE)}",
    ]
    for booking in bookings:
        lines.extend(_booking_event_lines(booking, force_confirmed=True))
    lines.extend(["END:VCALENDAR", ""])
    return "\r\n".join(lines).encode("utf-8")


def send_booking_notification(booking: dict) -> None:
    if not NOTIFY_ENABLED:
        raise RuntimeError("E-Mail-Benachrichtigungen sind deaktiviert")
    if not NOTIFY_EMAIL:
        raise RuntimeError("NOTIFY_EMAIL ist nicht gesetzt")
    if not SMTP_HOST or not SMTP_FROM:
        raise RuntimeError("SMTP_HOST oder SMTP_FROM fehlt")
    if SMTP_SECURITY not in {"starttls", "ssl", "none"}:
        raise RuntimeError("SMTP_SECURITY muss starttls, ssl oder none sein")

    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = NOTIFY_EMAIL
    requested = (booking.get("notification_type") == "new_request" or booking.get("status") == "requested")
    subject_prefix = "Neue Terminanfrage" if requested else "Neue Buchung"
    msg["Subject"] = f"{subject_prefix} · {booking['date']} {booking['start_time']} · {booking['service_name']}"
    msg.set_content(_mail_body(booking))
    msg.add_alternative(_mail_html(booking), subtype="html")
    msg.add_attachment(
        _booking_ics(booking),
        maintype="text",
        subtype="calendar",
        filename=f"chez-philipp-{booking['date']}-{booking['start_time'].replace(':', '')}{'-anfrage' if requested else ''}.ics",
        params={"method": "PUBLISH", "charset": "UTF-8"},
    )

    context = ssl.create_default_context()
    if SMTP_SECURITY == "ssl":
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT, context=context)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT)
    try:
        if SMTP_SECURITY == "starttls":
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def queue_booking_notification(conn, booking_id: str, notification_type: str = "new_booking") -> None:
    if not NOTIFY_ENABLED:
        return
    stamp = utc_iso()
    conn.execute(
        """INSERT INTO notification_outbox
           (id,booking_id,notification_type,status,attempts,next_attempt_at,last_error,created_at,updated_at,sent_at)
           VALUES(?,?,?,'pending',0,?,'',?,?,NULL)
           ON CONFLICT(booking_id,notification_type) DO NOTHING""",
        (str(uuid.uuid4()), booking_id, notification_type, stamp, stamp, stamp),
    )


def _retry_delay(attempts: int) -> int:
    # 1m, 2m, 4m, 8m ... capped at one hour.
    return min(3600, NOTIFY_RETRY_SECONDS * (2 ** max(0, attempts - 1)))


def process_notification_outbox(limit: int = 10, booking_id: str | None = None) -> int:
    if not NOTIFY_ENABLED:
        return 0
    if not _notification_lock.acquire(blocking=False):
        return 0
    processed = 0
    try:
        with connect(DB_PATH) as conn:
            params: list[object] = [utc_iso(), NOTIFY_MAX_ATTEMPTS]
            where = "n.status IN ('pending','failed') AND n.next_attempt_at<=? AND n.attempts<?"
            if booking_id:
                where += " AND n.booking_id=?"
                params.append(booking_id)
            params.append(max(1, limit))
            due = conn.execute(
                f"""SELECT n.id AS outbox_id, n.status AS outbox_status, n.attempts AS outbox_attempts,
                           n.notification_type, b.*
                    FROM notification_outbox n
                    JOIN bookings b ON b.id=n.booking_id
                    WHERE {where}
                    ORDER BY n.next_attempt_at,n.created_at LIMIT ?""",
                tuple(params),
            ).fetchall()

            for row in due:
                payload = dict(row)
                outbox_id = row["outbox_id"]
                attempts = int(row["outbox_attempts"]) + 1
                stamp = utc_iso()
                try:
                    send_booking_notification(payload)
                except Exception as exc:
                    delay = _retry_delay(attempts)
                    next_at = utc_iso(datetime.now(timezone.utc) + timedelta(seconds=delay))
                    safe_error = f"{type(exc).__name__}: {exc}"[:500]
                    conn.execute(
                        """UPDATE notification_outbox SET status='failed',attempts=?,next_attempt_at=?,last_error=?,updated_at=? WHERE id=?""",
                        (attempts, next_at, safe_error, stamp, outbox_id),
                    )
                else:
                    conn.execute(
                        """UPDATE notification_outbox SET status='sent',attempts=?,last_error='',sent_at=?,updated_at=? WHERE id=?""",
                        (attempts, stamp, stamp, outbox_id),
                    )
                processed += 1
    finally:
        _notification_lock.release()
    return processed


def _notification_worker() -> None:
    while True:
        try:
            process_notification_outbox(limit=20)
        except Exception as exc:
            app.logger.warning("Notification worker error: %s", exc)
        time.sleep(max(15, min(NOTIFY_RETRY_SECONDS, 300)))


def start_notification_worker() -> None:
    global _worker_started
    if not NOTIFY_ENABLED or _worker_started:
        return
    _worker_started = True
    threading.Thread(target=_notification_worker, name="notification-outbox", daemon=True).start()


@app.after_request
def security_headers(response):
    response.headers["Content-Security-Policy"] = CSP
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    origin = request.headers.get("Origin", "")
    if PWA_ALLOWED_ORIGIN and origin == PWA_ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, CF-Access-Client-Id, CF-Access-Client-Secret, X-Admin-Pin"
        response.headers["Access-Control-Max-Age"] = "600"
    return response


@app.route("/api/<path:_path>", methods=["OPTIONS"])
def api_options(_path):
    return Response(status=204)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION})


@app.get("/api/config")
def api_config():
    return jsonify({
        "title": APP_TITLE,
        "version": APP_VERSION,
        "app_url": APP_URL,
        "timezone": APP_TIMEZONE,
        "auth_enabled": AUTH_ENABLED,
        "backup_format": BACKUP_VERSION,
        "booking_notification_enabled": notification_configured(),
    })


@app.get("/api/services")
def api_services():
    with connect(DB_PATH) as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM services WHERE active=1 ORDER BY sort_order,name")]
    return jsonify(items)


@app.get("/api/nail-colors")
def api_nail_colors():
    with connect(DB_PATH) as conn:
        items = [dict(r) for r in conn.execute("SELECT * FROM nail_colors WHERE active=1 ORDER BY sort_order,name")]
    return jsonify(items)


@app.get("/api/availability")
def api_availability():
    booking_date = request.args.get("date", "")
    service_id = request.args.get("service_id", "")
    if not booking_date or not service_id:
        return json_error("date und service_id sind erforderlich")
    try:
        with connect(DB_PATH) as conn:
            slots = availability(conn, booking_date, service_id)
    except ValueError as exc:
        return json_error(str(exc))
    return jsonify({"date": booking_date, "service_id": service_id, "slots": slots})


@app.get("/api/availability-days")
def api_availability_days():
    service_id = request.args.get("service_id", "")
    try:
        days = max(1, min(60, int(request.args.get("days", "28"))))
    except ValueError:
        days = 28
    if not service_id:
        return json_error("service_id ist erforderlich")
    today = datetime.now(TZ).date()
    result = []
    try:
        with connect(DB_PATH) as conn:
            for offset in range(days):
                value = (today + timedelta(days=offset)).isoformat()
                slots = availability(conn, value, service_id)
                result.append({"date": value, "count": len(slots)})
    except ValueError as exc:
        return json_error(str(exc))
    return jsonify({"service_id": service_id, "days": result})


@app.post("/api/bookings")
def api_create_booking():
    payload = request.get_json(silent=True) or {}
    required = ["service_id", "date", "start_time"]
    if any(not str(payload.get(key, "")).strip() for key in required):
        return json_error("Leistung, Datum und Uhrzeit sind erforderlich")
    name = BOOKING_CUSTOMER_NAME
    email = ""
    phone = ""
    notes = str(payload.get("notes", "")).strip()[:1500]
    booking_date = str(payload["date"])
    start_time = str(payload["start_time"])
    service_id = str(payload["service_id"])
    color_id = str(payload.get("nail_color_id", "")).strip()[:80]
    booking_mode = str(payload.get("booking_mode", "confirmed")).strip().lower()
    if booking_mode not in {"confirmed", "requested"}:
        return json_error("Ungültiger Buchungsmodus")
    try:
        booking_day = valid_date(booking_date)
        start_minutes = parse_minutes(start_time)
        if not 0 <= start_minutes < 24 * 60:
            raise ValueError
    except (ValueError, TypeError):
        return json_error("Ungültiges Datum oder ungültige Uhrzeit")
    current = datetime.now(TZ)
    if booking_day < current.date() or (booking_day == current.date() and start_minutes <= current.hour * 60 + current.minute):
        return json_error("Der gewünschte Termin liegt in der Vergangenheit")

    with connect(DB_PATH) as conn:
        service = conn.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
        if not service:
            return json_error("Leistung nicht gefunden", 404)
        color = None
        if int(service["color_enabled"]):
            if not color_id:
                return json_error("Bitte eine Farbe auswählen")
            color = conn.execute("SELECT * FROM nail_colors WHERE id=? AND active=1", (color_id,)).fetchone()
            if not color:
                return json_error("Farbe nicht gefunden", 404)
        end_minutes = start_minutes + int(service["duration_min"])
        if end_minutes >= 24 * 60:
            return json_error("Der gewünschte Termin würde über Mitternacht hinausgehen")
        end_time = minutes_to_time(end_minutes)
        if booking_mode == "confirmed":
            try:
                free_slots = availability(conn, booking_date, service_id)
            except ValueError as exc:
                return json_error(str(exc))
            if start_time not in free_slots:
                return json_error("Dieser Termin ist nicht mehr verfügbar", 409)
        elif has_confirmed_conflict(conn, booking_date, start_time, end_time):
            return json_error("Zu dieser Zeit besteht bereits ein bestätigter Termin", 409)
        booking_id = str(uuid.uuid4())
        code = generate_code(conn)
        stamp = now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if booking_mode == "confirmed" and start_time not in availability(conn, booking_date, service_id):
                conn.execute("ROLLBACK")
                return json_error("Dieser Termin wurde gerade vergeben", 409)
            if booking_mode == "requested" and has_confirmed_conflict(conn, booking_date, start_time, end_time):
                conn.execute("ROLLBACK")
                return json_error("Zu dieser Zeit besteht bereits ein bestätigter Termin", 409)
            conn.execute(
                """INSERT INTO bookings
                (id,public_code,customer_name,customer_email,customer_phone,service_id,service_name,price_label,
                 nail_color_id,nail_color_name,nail_color_hex,date,start_time,end_time,notes,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    booking_id, code, name, email, phone, service_id, service["name"], service["price_label"],
                    color["id"] if color else "", color["name"] if color else "", color["hex_color"] if color else "",
                    booking_date, start_time, end_time, notes, booking_mode, stamp, stamp,
                ),
            )
            queue_booking_notification(conn, booking_id, "new_request" if booking_mode == "requested" else "new_booking")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()

    # Try immediately, but a mail failure never rolls back the confirmed booking.
    if NOTIFY_ENABLED:
        try:
            process_notification_outbox(limit=1, booking_id=booking_id)
        except Exception as exc:
            app.logger.warning("Immediate booking notification failed: %s", exc)
    return jsonify(dict(row)), 201


@app.get("/api/bookings/by-code/<code>")
def api_booking_by_code(code):
    code = code.strip().upper()[:32]
    with connect(DB_PATH) as conn:
        row = conn.execute(
            """SELECT id,public_code,customer_name,service_id,service_name,price_label,nail_color_id,nail_color_name,nail_color_hex,
                      date,start_time,end_time,status,created_at
               FROM bookings WHERE public_code=?""",
            (code,),
        ).fetchone()
    if not row:
        return json_error("Buchung nicht gefunden", 404)
    return jsonify(dict(row))


@app.get("/api/admin/state")
def api_admin_state():
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        services = [dict(r) for r in conn.execute("SELECT * FROM services ORDER BY sort_order,name")]
        colors = [dict(r) for r in conn.execute("SELECT * FROM nail_colors ORDER BY sort_order,name")]
        hours = [dict(r) for r in conn.execute("SELECT * FROM opening_hours ORDER BY weekday")]
        overrides = [dict(r) for r in conn.execute("SELECT * FROM availability_overrides ORDER BY date,start_time")]
        bookings = [dict(r) for r in conn.execute(
            """SELECT b.*, n.status AS notification_status, n.attempts AS notification_attempts,
                      n.last_error AS notification_last_error, n.sent_at AS notification_sent_at
               FROM bookings b LEFT JOIN notification_outbox n
                 ON n.booking_id=b.id
               ORDER BY b.date DESC,b.start_time DESC LIMIT 500"""
        )]
    feed_base = APP_URL or request.host_url.rstrip("/")
    return jsonify({
        "services": services,
        "nail_colors": colors,
        "opening_hours": hours,
        "availability_overrides": overrides,
        "bookings": bookings,
        "notification_enabled": notification_configured(),
        "calendar_feed_enabled": bool(CALENDAR_FEED_TOKEN),
        "calendar_feed_url": f"{feed_base}/calendar.ics?token={CALENDAR_FEED_TOKEN}" if CALENDAR_FEED_TOKEN else "",
    })


@app.put("/api/admin/services")
def api_admin_services():
    denied = require_admin()
    if denied:
        return denied
    items = request.get_json(silent=True)
    if not isinstance(items, list):
        return json_error("Ungültige Leistungsliste")
    stamp = now_iso()
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for index, item in enumerate(items):
                service_id = str(item.get("id") or uuid.uuid4())[:80]
                name = str(item.get("name", "")).strip()[:120]
                if not name:
                    raise ValueError("Jede Leistung benötigt einen Namen")
                duration = max(5, min(480, int(item.get("duration_min", 30))))
                conn.execute(
                    """INSERT INTO services
                    (id,name,short_description,description,price_label,duration_min,icon,color_enabled,active,sort_order,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, short_description=excluded.short_description, description=excluded.description,
                    price_label=excluded.price_label, duration_min=excluded.duration_min, icon=excluded.icon,
                    color_enabled=excluded.color_enabled, active=excluded.active, sort_order=excluded.sort_order, updated_at=excluded.updated_at""",
                    (
                        service_id, name, str(item.get("short_description", ""))[:220], str(item.get("description", ""))[:2000],
                        str(item.get("price_label", ""))[:80], duration, str(item.get("icon", ""))[:12],
                        1 if item.get("color_enabled") else 0, 1 if item.get("active", True) else 0,
                        int(item.get("sort_order", index * 10)), str(item.get("created_at") or stamp), stamp,
                    ),
                )
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            return json_error(str(exc))
    return jsonify({"status": "ok"})


@app.put("/api/admin/nail-colors")
def api_admin_nail_colors():
    denied = require_admin()
    if denied:
        return denied
    items = request.get_json(silent=True)
    if not isinstance(items, list):
        return json_error("Ungültige Farbliste")
    stamp = now_iso()
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for index, item in enumerate(items):
                color_id = str(item.get("id") or uuid.uuid4())[:80]
                name = str(item.get("name", "")).strip()[:100]
                color_hex = str(item.get("hex_color", "#B9B2AA")).strip().upper()[:16]
                if not name:
                    raise ValueError("Jede Farbe benötigt einen Namen")
                if len(color_hex) != 7 or color_hex[0] != "#" or any(ch not in string.hexdigits for ch in color_hex[1:]):
                    raise ValueError(f"Ungültiger Farbwert bei {name}")
                conn.execute(
                    """INSERT INTO nail_colors(id,name,hex_color,active,sort_order,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                       name=excluded.name,hex_color=excluded.hex_color,active=excluded.active,sort_order=excluded.sort_order,updated_at=excluded.updated_at""",
                    (color_id, name, color_hex, 1 if item.get("active", True) else 0, int(item.get("sort_order", index * 10)), str(item.get("created_at") or stamp), stamp),
                )
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            return json_error(str(exc))
    return jsonify({"status": "ok"})


@app.put("/api/admin/opening-hours")
def api_admin_hours():
    denied = require_admin()
    if denied:
        return denied
    items = request.get_json(silent=True)
    if not isinstance(items, list) or len(items) != 7:
        return json_error("Es werden sieben Wochentage erwartet")
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item in items:
                weekday = int(item["weekday"])
                start = str(item["start_time"])
                end = str(item["end_time"])
                interval = int(item.get("slot_interval_min", 30))
                if not 0 <= weekday <= 6 or parse_minutes(start) >= parse_minutes(end):
                    raise ValueError("Ungültige Öffnungszeit")
                conn.execute(
                    """INSERT INTO opening_hours(weekday,enabled,start_time,end_time,slot_interval_min)
                    VALUES(?,?,?,?,?) ON CONFLICT(weekday) DO UPDATE SET
                    enabled=excluded.enabled,start_time=excluded.start_time,end_time=excluded.end_time,slot_interval_min=excluded.slot_interval_min""",
                    (weekday, 1 if item.get("enabled") else 0, start, end, max(5, min(240, interval))),
                )
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            return json_error(str(exc))
    return jsonify({"status": "ok"})


@app.put("/api/admin/availability-overrides")
def api_admin_availability_overrides():
    denied = require_admin()
    if denied:
        return denied
    items = request.get_json(silent=True)
    if not isinstance(items, list):
        return json_error("Ungültige Ausnahmeliste")
    normalized = []
    try:
        for item in items[:500]:
            day = str(item.get("date", "")).strip()
            valid_date(day)
            kind = str(item.get("kind", "available"))
            if kind not in {"available", "closed"}:
                raise ValueError("Ungültiger Ausnahmetyp")
            start = str(item.get("start_time", "")).strip()
            end = str(item.get("end_time", "")).strip()
            if kind == "available" and (parse_minutes(start) >= parse_minutes(end)):
                raise ValueError("Bei einer Freigabe muss 'Bis' nach 'Von' liegen")
            normalized.append({
                "id": str(item.get("id") or uuid.uuid4()), "date": day, "kind": kind,
                "start_time": start if kind == "available" else "", "end_time": end if kind == "available" else "",
            })
    except (ValueError, TypeError, KeyError) as exc:
        return json_error(str(exc) or "Ungültige Verfügbarkeitsausnahme")
    stamp = now_iso()
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM availability_overrides")
            for item in normalized:
                conn.execute(
                    "INSERT INTO availability_overrides(id,date,kind,start_time,end_time,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    (item["id"], item["date"], item["kind"], item["start_time"], item["end_time"], stamp, stamp),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return jsonify({"status":"ok"})


@app.post("/api/admin/bookings/<booking_id>/confirm")
def api_admin_confirm_request(booking_id):
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if not row:
            return json_error("Terminanfrage nicht gefunden", 404)
        if row["status"] != "requested":
            return json_error("Nur offene Terminanfragen können bestätigt werden", 409)
        conn.execute("BEGIN IMMEDIATE")
        try:
            if has_confirmed_conflict(conn, row["date"], row["start_time"], row["end_time"], booking_id):
                conn.execute("ROLLBACK")
                return json_error("Der Zeitraum ist inzwischen durch einen bestätigten Termin belegt", 409)
            conn.execute("UPDATE bookings SET status='confirmed',updated_at=? WHERE id=?", (now_iso(), booking_id))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return jsonify({"status":"confirmed"})


@app.post("/api/admin/bookings/<booking_id>/reject")
def api_admin_reject_request(booking_id):
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        conn.execute("UPDATE bookings SET status='rejected',updated_at=? WHERE id=? AND status='requested'", (now_iso(), booking_id))
    return jsonify({"status":"rejected"})


@app.delete("/api/admin/bookings/<booking_id>")
def api_admin_delete_booking(booking_id):
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        conn.execute("UPDATE bookings SET status=CASE WHEN status='requested' THEN 'rejected' ELSE 'cancelled' END, updated_at=? WHERE id=?", (now_iso(), booking_id))
    # Deliberately no cancellation e-mail: only new bookings notify.
    return jsonify({"status": "ok"})


@app.post("/api/admin/notifications/<booking_id>/retry")
def api_admin_retry_notification(booking_id):
    denied = require_admin()
    if denied:
        return denied
    if not NOTIFY_ENABLED:
        return json_error("E-Mail-Benachrichtigungen sind deaktiviert", 409)
    stamp = utc_iso()
    with connect(DB_PATH) as conn:
        row = conn.execute("SELECT id,notification_type FROM notification_outbox WHERE booking_id=? ORDER BY created_at DESC LIMIT 1", (booking_id,)).fetchone()
        if not row:
            booking = conn.execute("SELECT id FROM bookings WHERE id=?", (booking_id,)).fetchone()
            if not booking:
                return json_error("Buchung nicht gefunden", 404)
            booking_row = conn.execute("SELECT status FROM bookings WHERE id=?", (booking_id,)).fetchone()
            queue_booking_notification(conn, booking_id, "new_request" if booking_row and booking_row["status"] == "requested" else "new_booking")
        else:
            conn.execute(
                """UPDATE notification_outbox SET status='pending',attempts=0,next_attempt_at=?,last_error='',updated_at=? WHERE booking_id=?""",
                (stamp, stamp, booking_id),
            )
    process_notification_outbox(limit=1, booking_id=booking_id)
    with connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status,attempts,last_error,sent_at FROM notification_outbox WHERE booking_id=?",
            (booking_id,),
        ).fetchone()
    return jsonify(dict(row) if row else {"status": "pending"})


@app.get("/api/admin/export")
def api_admin_export():
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        payload = export_payload(conn)
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    response = Response(body, mimetype="application/json")
    response.headers["Content-Disposition"] = f'attachment; filename="chez-philipp-backup-{datetime.now(TZ).strftime("%Y%m%d")}.json"'
    return response


@app.post("/api/admin/import/preview")
def api_admin_import_preview():
    denied = require_admin()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    try:
        counts = validate_backup(payload)
    except ValueError as exc:
        return json_error(str(exc))
    return jsonify({"valid": True, "counts": counts, "strategies": ["replace", "merge"]})


@app.post("/api/admin/import/apply")
def api_admin_import_apply():
    denied = require_admin()
    if denied:
        return denied
    payload = request.get_json(silent=True) or {}
    strategy = request.args.get("strategy", "replace")
    if strategy not in {"replace", "merge"}:
        return json_error("Unbekannte Importstrategie")
    try:
        counts = validate_backup(payload)
    except ValueError as exc:
        return json_error(str(exc))
    backup_database(DB_PATH, BACKUPS_DIR, BACKUP_KEEP, "pre-import")
    data = payload["data"]
    backup_version = int(payload.get("version", 1))
    with connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            if strategy == "replace":
                conn.execute("DELETE FROM bookings")
                conn.execute("DELETE FROM opening_hours")
                conn.execute("DELETE FROM availability_overrides")
                conn.execute("DELETE FROM services")
                if backup_version >= 2:
                    conn.execute("DELETE FROM nail_colors")
            for index, item in enumerate(data.get("services", [])):
                service_id = str(item.get("id") or uuid.uuid4())
                inferred_color = service_id in {"hands", "feet", "hands-foot-massage", "hands-feet"}
                conn.execute(
                    """INSERT INTO services(id,name,short_description,description,price_label,duration_min,icon,color_enabled,active,sort_order,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,short_description=excluded.short_description,description=excluded.description,price_label=excluded.price_label,
                    duration_min=excluded.duration_min,icon=excluded.icon,color_enabled=excluded.color_enabled,active=excluded.active,
                    sort_order=excluded.sort_order,updated_at=excluded.updated_at""",
                    (
                        service_id, item.get("name", "Leistung"), item.get("short_description", ""), item.get("description", ""),
                        item.get("price_label", ""), item.get("duration_min", 30), item.get("icon", ""),
                        item.get("color_enabled", 1 if inferred_color else 0), item.get("active", 1), item.get("sort_order", index * 10),
                        item.get("created_at") or now_iso(), item.get("updated_at") or now_iso(),
                    ),
                )
            for index, item in enumerate(data.get("nail_colors", [])):
                conn.execute(
                    """INSERT INTO nail_colors(id,name,hex_color,active,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET name=excluded.name,hex_color=excluded.hex_color,active=excluded.active,
                    sort_order=excluded.sort_order,updated_at=excluded.updated_at""",
                    (
                        item.get("id") or str(uuid.uuid4()), item.get("name", "Farbe"), item.get("hex_color", "#B9B2AA"),
                        item.get("active", 1), item.get("sort_order", index * 10), item.get("created_at") or now_iso(), item.get("updated_at") or now_iso(),
                    ),
                )
            for item in data.get("opening_hours", []):
                conn.execute(
                    """INSERT INTO opening_hours(weekday,enabled,start_time,end_time,slot_interval_min) VALUES(?,?,?,?,?)
                    ON CONFLICT(weekday) DO UPDATE SET enabled=excluded.enabled,start_time=excluded.start_time,end_time=excluded.end_time,slot_interval_min=excluded.slot_interval_min""",
                    tuple(item.get(k) for k in ["weekday", "enabled", "start_time", "end_time", "slot_interval_min"]),
                )
            if backup_version >= 3:
                for item in data.get("availability_overrides", []):
                    conn.execute(
                        """INSERT INTO availability_overrides(id,date,kind,start_time,end_time,created_at,updated_at) VALUES(?,?,?,?,?,?,?)
                        ON CONFLICT(id) DO UPDATE SET date=excluded.date,kind=excluded.kind,start_time=excluded.start_time,end_time=excluded.end_time,updated_at=excluded.updated_at""",
                        (item.get("id") or str(uuid.uuid4()), item.get("date"), item.get("kind", "available"), item.get("start_time", ""), item.get("end_time", ""), item.get("created_at") or now_iso(), item.get("updated_at") or now_iso()),
                    )
            for item in data.get("bookings", []):
                conn.execute(
                    """INSERT INTO bookings(id,public_code,customer_name,customer_email,customer_phone,service_id,service_name,price_label,
                    nail_color_id,nail_color_name,nail_color_hex,date,start_time,end_time,notes,status,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    public_code=excluded.public_code,customer_name=excluded.customer_name,customer_email=excluded.customer_email,customer_phone=excluded.customer_phone,
                    service_id=excluded.service_id,service_name=excluded.service_name,price_label=excluded.price_label,nail_color_id=excluded.nail_color_id,
                    nail_color_name=excluded.nail_color_name,nail_color_hex=excluded.nail_color_hex,date=excluded.date,start_time=excluded.start_time,
                    end_time=excluded.end_time,notes=excluded.notes,status=excluded.status,updated_at=excluded.updated_at""",
                    (
                        item.get("id"), item.get("public_code"), item.get("customer_name"), item.get("customer_email", ""), item.get("customer_phone", ""),
                        item.get("service_id"), item.get("service_name"), item.get("price_label", ""), item.get("nail_color_id", ""),
                        item.get("nail_color_name", ""), item.get("nail_color_hex", ""), item.get("date"), item.get("start_time"), item.get("end_time"),
                        item.get("notes", ""), item.get("status", "confirmed"), item.get("created_at") or now_iso(), item.get("updated_at") or now_iso(),
                    ),
                )
            conn.execute("COMMIT")
        except Exception as exc:
            conn.execute("ROLLBACK")
            return json_error(f"Import fehlgeschlagen: {exc}")
    return jsonify({"status": "ok", "counts": counts, "strategy": strategy})


@app.get("/api/admin/backup")
def api_admin_backup():
    denied = require_admin()
    if denied:
        return denied
    path = backup_database(DB_PATH, BACKUPS_DIR, BACKUP_KEEP, "manual")
    return jsonify({"status": "ok", "file": path.name if path else None})


@app.get("/calendar.ics")
def calendar_feed():
    supplied = request.args.get("token", "")
    if not CALENDAR_FEED_TOKEN or not supplied or not hmac.compare_digest(supplied, CALENDAR_FEED_TOKEN):
        return Response(status=404)
    with connect(DB_PATH) as conn:
        bookings = [dict(row) for row in conn.execute(
            """SELECT * FROM bookings WHERE status='confirmed' ORDER BY date,start_time"""
        ).fetchall()]
    response = Response(_calendar_feed_ics(bookings), mimetype="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = 'inline; filename="chez-philipp.ics"'
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/<path:path>")
def static_files(path):
    file_path = Path(app.static_folder) / path
    if file_path.is_file():
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")


start_notification_worker()
