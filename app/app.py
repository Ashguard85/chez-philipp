from __future__ import annotations

import hmac
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

APP_VERSION = "2.0.0"
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
SMTP_PORT = max(1, min(65535, int(os.getenv("SMTP_PORT", "587"))))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()
SMTP_SECURITY = os.getenv("SMTP_SECURITY", "starttls").strip().lower()
SMTP_TIMEOUT = max(3, min(60, int(os.getenv("SMTP_TIMEOUT", "12"))))
NOTIFY_RETRY_SECONDS = max(15, int(os.getenv("NOTIFY_RETRY_SECONDS", "60")))
NOTIFY_MAX_ATTEMPTS = max(1, min(100, int(os.getenv("NOTIFY_MAX_ATTEMPTS", "12"))))

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


def availability(conn, booking_date: str, service_id: str) -> list[str]:
    day = valid_date(booking_date)
    service = conn.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
    if not service:
        raise ValueError("Leistung nicht gefunden")
    hours = conn.execute("SELECT * FROM opening_hours WHERE weekday=?", (day.weekday(),)).fetchone()
    if not hours or not hours["enabled"]:
        return []
    start = parse_minutes(hours["start_time"])
    end = parse_minutes(hours["end_time"])
    duration = int(service["duration_min"])
    step = int(hours["slot_interval_min"])
    occupied = [
        (parse_minutes(row["start_time"]), parse_minutes(row["end_time"]))
        for row in conn.execute(
            "SELECT start_time,end_time FROM bookings WHERE date=? AND status='confirmed'",
            (booking_date,),
        ).fetchall()
    ]
    current = datetime.now(TZ)
    slots = []
    cursor = start
    while cursor + duration <= end:
        slot_end = cursor + duration
        overlaps = any(cursor < busy_end and slot_end > busy_start for busy_start, busy_end in occupied)
        in_past = day == current.date() and cursor <= current.hour * 60 + current.minute
        if not overlaps and not in_past and day >= current.date():
            slots.append(minutes_to_time(cursor))
        cursor += step
    return slots


def notification_configured() -> bool:
    return bool(NOTIFY_ENABLED and NOTIFY_EMAIL and SMTP_HOST and SMTP_FROM)


def _mail_body(booking: dict) -> str:
    lines = [
        "Neue Buchung bei Chez Philipp",
        "",
        f"Termin: {booking['date']} · {booking['start_time']}–{booking['end_time']} Uhr",
        f"Behandlung: {booking['service_name']}",
    ]
    if booking.get("nail_color_name"):
        lines.append(f"Farbe: {booking['nail_color_name']}")
    lines.extend([
        f"Gebucht von: {booking['customer_name']}",
        f"Buchungscode: {booking['public_code']}",
    ])
    if booking.get("customer_phone"):
        lines.append(f"Telefon: {booking['customer_phone']}")
    if booking.get("customer_email"):
        lines.append(f"E-Mail: {booking['customer_email']}")
    if booking.get("notes"):
        lines.extend(["", f"Notiz: {booking['notes']}"])
    lines.extend(["", "Diese Nachricht wurde automatisch nach einer neuen Server-Buchung versendet."])
    return "\n".join(lines)


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
    msg["Subject"] = f"Neue Buchung · {booking['date']} {booking['start_time']} · {booking['service_name']}"
    msg.set_content(_mail_body(booking))

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


def queue_booking_notification(conn, booking_id: str) -> None:
    if not NOTIFY_ENABLED:
        return
    stamp = utc_iso()
    conn.execute(
        """INSERT INTO notification_outbox
           (id,booking_id,notification_type,status,attempts,next_attempt_at,last_error,created_at,updated_at,sent_at)
           VALUES(?,?, 'new_booking','pending',0,?,'',?,?,NULL)
           ON CONFLICT(booking_id,notification_type) DO NOTHING""",
        (str(uuid.uuid4()), booking_id, stamp, stamp, stamp),
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
                f"""SELECT n.*, b.* FROM notification_outbox n
                    JOIN bookings b ON b.id=n.booking_id
                    WHERE {where}
                    ORDER BY n.next_attempt_at,n.created_at LIMIT ?""",
                tuple(params),
            ).fetchall()

            for row in due:
                payload = dict(row)
                outbox_id = row["id"]
                attempts = int(row["attempts"]) + 1
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


@app.post("/api/bookings")
def api_create_booking():
    payload = request.get_json(silent=True) or {}
    required = ["customer_name", "service_id", "date", "start_time"]
    if any(not str(payload.get(key, "")).strip() for key in required):
        return json_error("Name, Leistung, Datum und Uhrzeit sind erforderlich")
    name = str(payload["customer_name"]).strip()[:120]
    email = str(payload.get("customer_email", "")).strip()[:180]
    phone = str(payload.get("customer_phone", "")).strip()[:80]
    notes = str(payload.get("notes", "")).strip()[:1500]
    booking_date = str(payload["date"])
    start_time = str(payload["start_time"])
    service_id = str(payload["service_id"])
    color_id = str(payload.get("nail_color_id", "")).strip()[:80]
    try:
        valid_date(booking_date)
    except ValueError:
        return json_error("Ungültiges Datum")

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
        try:
            free_slots = availability(conn, booking_date, service_id)
        except ValueError as exc:
            return json_error(str(exc))
        if start_time not in free_slots:
            return json_error("Dieser Termin ist nicht mehr verfügbar", 409)
        end_time = minutes_to_time(parse_minutes(start_time) + int(service["duration_min"]))
        booking_id = str(uuid.uuid4())
        code = generate_code(conn)
        stamp = now_iso()
        try:
            conn.execute("BEGIN IMMEDIATE")
            if start_time not in availability(conn, booking_date, service_id):
                conn.execute("ROLLBACK")
                return json_error("Dieser Termin wurde gerade vergeben", 409)
            conn.execute(
                """INSERT INTO bookings
                (id,public_code,customer_name,customer_email,customer_phone,service_id,service_name,price_label,
                 nail_color_id,nail_color_name,nail_color_hex,date,start_time,end_time,notes,status,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    booking_id, code, name, email, phone, service_id, service["name"], service["price_label"],
                    color["id"] if color else "", color["name"] if color else "", color["hex_color"] if color else "",
                    booking_date, start_time, end_time, notes, "confirmed", stamp, stamp,
                ),
            )
            queue_booking_notification(conn, booking_id)
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
        bookings = [dict(r) for r in conn.execute(
            """SELECT b.*, n.status AS notification_status, n.attempts AS notification_attempts,
                      n.last_error AS notification_last_error, n.sent_at AS notification_sent_at
               FROM bookings b LEFT JOIN notification_outbox n
                 ON n.booking_id=b.id AND n.notification_type='new_booking'
               ORDER BY b.date DESC,b.start_time DESC LIMIT 500"""
        )]
    return jsonify({
        "services": services,
        "nail_colors": colors,
        "opening_hours": hours,
        "bookings": bookings,
        "notification_enabled": notification_configured(),
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


@app.delete("/api/admin/bookings/<booking_id>")
def api_admin_delete_booking(booking_id):
    denied = require_admin()
    if denied:
        return denied
    with connect(DB_PATH) as conn:
        conn.execute("UPDATE bookings SET status='cancelled', updated_at=? WHERE id=?", (now_iso(), booking_id))
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
        row = conn.execute("SELECT id FROM notification_outbox WHERE booking_id=? AND notification_type='new_booking'", (booking_id,)).fetchone()
        if not row:
            booking = conn.execute("SELECT id FROM bookings WHERE id=?", (booking_id,)).fetchone()
            if not booking:
                return json_error("Buchung nicht gefunden", 404)
            queue_booking_notification(conn, booking_id)
        else:
            conn.execute(
                """UPDATE notification_outbox SET status='pending',attempts=0,next_attempt_at=?,last_error='',updated_at=? WHERE booking_id=? AND notification_type='new_booking'""",
                (stamp, stamp, booking_id),
            )
    process_notification_outbox(limit=1, booking_id=booking_id)
    with connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT status,attempts,last_error,sent_at FROM notification_outbox WHERE booking_id=? AND notification_type='new_booking'",
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
