from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 3
BACKUP_VERSION = 3

DEFAULT_SERVICES = [
    {
        "id": "hands",
        "name": "Signature Manicure",
        "short_description": "Präzise Hand- und Nagelpflege",
        "description": "Form, Pflege und ein makelloses Finish – ruhig, sorgfältig und auf deine Wünsche abgestimmt.",
        "price_label": "1 Küsschen",
        "duration_min": 45,
        "icon": "H",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 10,
    },
    {
        "id": "feet",
        "name": "Signature Pedicure",
        "short_description": "Entspannende Pflege für deine Füsse",
        "description": "Ein gepflegtes, entspanntes Finish mit Zeit für Details und einer angenehm ruhigen Behandlung.",
        "price_label": "1 Küsschen",
        "duration_min": 45,
        "icon": "F",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 20,
    },
    {
        "id": "hands-foot-massage",
        "name": "Manicure & Foot Ritual",
        "short_description": "Handpflege mit Fussmassage",
        "description": "Signature Manicure kombiniert mit einer wohltuenden Fussmassage – für ein besonders entspanntes Erlebnis.",
        "price_label": "1 Küsschen",
        "duration_min": 75,
        "icon": "HF",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 30,
    },
    {
        "id": "hands-feet",
        "name": "Full Care Ritual",
        "short_description": "Komplettpflege für Hände und Füsse",
        "description": "Das vollständige Pflegeprogramm mit ausreichend Zeit für Hände, Füsse und ein hochwertiges Finish.",
        "price_label": "1 Küsschen",
        "duration_min": 90,
        "icon": "FC",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 40,
    },
    {
        "id": "foot-massage",
        "name": "Foot Massage",
        "short_description": "Entspannung für müde Füsse",
        "description": "Eine fokussierte, wohltuende Massage für eine bewusste Pause und spürbare Entspannung.",
        "price_label": "1 Küsschen",
        "duration_min": 30,
        "icon": "FM",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 50,
    },
    {
        "id": "philipp-exclusive",
        "name": "Philipp's Private Ritual",
        "short_description": "Die persönliche Signature-Behandlung",
        "description": "Die exklusive Behandlung mit Philipp – individuell, persönlich und mit besonderer Aufmerksamkeit.",
        "price_label": "1 Küsschen",
        "duration_min": 60,
        "icon": "P",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 60,
    },
]

DEFAULT_NAIL_COLORS = [
    {"id": "nude", "name": "Nude", "hex_color": "#D8B7A6", "active": 1, "sort_order": 10},
    {"id": "blush", "name": "Blush", "hex_color": "#E6B8B4", "active": 1, "sort_order": 20},
    {"id": "rose", "name": "Rosé", "hex_color": "#C88F95", "active": 1, "sort_order": 30},
    {"id": "red", "name": "Classic Red", "hex_color": "#A8323D", "active": 1, "sort_order": 40},
    {"id": "bordeaux", "name": "Bordeaux", "hex_color": "#6D2431", "active": 1, "sort_order": 50},
    {"id": "taupe", "name": "Taupe", "hex_color": "#8C786D", "active": 1, "sort_order": 60},
    {"id": "milky-white", "name": "Milky White", "hex_color": "#F2EEE6", "active": 1, "sort_order": 70},
    {"id": "black", "name": "Black", "hex_color": "#292524", "active": 1, "sort_order": 80},
    {"id": "french", "name": "French", "hex_color": "#E8D7CB", "active": 1, "sort_order": 90},
    {"id": "decide-later", "name": "Vor Ort entscheiden", "hex_color": "#B9B2AA", "active": 1, "sort_order": 100},
]

DEFAULT_HOURS = {
    0: {"enabled": 1, "start_time": "09:00", "end_time": "18:00", "slot_interval_min": 30},
    1: {"enabled": 1, "start_time": "09:00", "end_time": "18:00", "slot_interval_min": 30},
    2: {"enabled": 1, "start_time": "09:00", "end_time": "18:00", "slot_interval_min": 30},
    3: {"enabled": 1, "start_time": "09:00", "end_time": "18:00", "slot_interval_min": 30},
    4: {"enabled": 1, "start_time": "09:00", "end_time": "18:00", "slot_interval_min": 30},
    5: {"enabled": 0, "start_time": "09:00", "end_time": "16:00", "slot_interval_min": 30},
    6: {"enabled": 0, "start_time": "09:00", "end_time": "16:00", "slot_interval_min": 30},
}


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    if not _table_exists(conn, table):
        return False
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _seed_defaults(conn: sqlite3.Connection) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    if conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        conn.executemany(
            """INSERT INTO services
            (id,name,short_description,description,price_label,duration_min,icon,color_enabled,active,sort_order,created_at,updated_at)
            VALUES (:id,:name,:short_description,:description,:price_label,:duration_min,:icon,:color_enabled,:active,:sort_order,:created_at,:updated_at)""",
            [{**service, "created_at": now, "updated_at": now} for service in DEFAULT_SERVICES],
        )
    if conn.execute("SELECT COUNT(*) FROM opening_hours").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO opening_hours (weekday,enabled,start_time,end_time,slot_interval_min) VALUES (?,?,?,?,?)",
            [(day, v["enabled"], v["start_time"], v["end_time"], v["slot_interval_min"]) for day, v in DEFAULT_HOURS.items()],
        )
    if conn.execute("SELECT COUNT(*) FROM nail_colors").fetchone()[0] == 0:
        conn.executemany(
            """INSERT INTO nail_colors(id,name,hex_color,active,sort_order,created_at,updated_at)
               VALUES(:id,:name,:hex_color,:active,:sort_order,:created_at,:updated_at)""",
            [{**color, "created_at": now, "updated_at": now} for color in DEFAULT_NAIL_COLORS],
        )


def init_db(db_path: Path, backups_dir: Path, backup_keep: int) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    existing_version = 0
    if db_path.exists():
        try:
            with connect(db_path) as conn:
                if _table_exists(conn, "meta"):
                    row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                    existing_version = int(row[0]) if row else 0
        except (sqlite3.Error, ValueError):
            existing_version = 0
    if db_path.exists() and existing_version < SCHEMA_VERSION:
        backup_database(db_path, backups_dir, backup_keep, "pre-migration")

    with connect(db_path) as conn:
        # v3 widens booking states to support explicit appointment requests.
        # Rebuild the two related tables once, after the automatic pre-migration backup.
        if existing_version and existing_version < 3 and _table_exists(conn, "bookings"):
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("ALTER TABLE bookings RENAME TO bookings_v2")
                if _table_exists(conn, "notification_outbox"):
                    conn.execute("ALTER TABLE notification_outbox RENAME TO notification_outbox_v2")
                conn.execute(
                    """CREATE TABLE bookings (
                        id TEXT PRIMARY KEY, public_code TEXT NOT NULL UNIQUE, customer_name TEXT NOT NULL,
                        customer_email TEXT NOT NULL DEFAULT '', customer_phone TEXT NOT NULL DEFAULT '',
                        service_id TEXT NOT NULL, service_name TEXT NOT NULL, price_label TEXT NOT NULL DEFAULT '',
                        nail_color_id TEXT NOT NULL DEFAULT '', nail_color_name TEXT NOT NULL DEFAULT '', nail_color_hex TEXT NOT NULL DEFAULT '',
                        date TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','requested','cancelled','rejected')),
                        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                        FOREIGN KEY(service_id) REFERENCES services(id) ON UPDATE CASCADE
                    )"""
                )
                color_id_expr = "nail_color_id" if _column_exists(conn, "bookings_v2", "nail_color_id") else "''"
                color_name_expr = "nail_color_name" if _column_exists(conn, "bookings_v2", "nail_color_name") else "''"
                color_hex_expr = "nail_color_hex" if _column_exists(conn, "bookings_v2", "nail_color_hex") else "''"
                conn.execute(
                    f"""INSERT INTO bookings(
                        id,public_code,customer_name,customer_email,customer_phone,service_id,service_name,price_label,
                        nail_color_id,nail_color_name,nail_color_hex,date,start_time,end_time,notes,status,created_at,updated_at
                    )
                    SELECT id,public_code,customer_name,customer_email,customer_phone,service_id,service_name,price_label,
                           {color_id_expr},{color_name_expr},{color_hex_expr},date,start_time,end_time,notes,status,created_at,updated_at
                    FROM bookings_v2"""
                )
                conn.execute(
                    """CREATE TABLE notification_outbox (
                        id TEXT PRIMARY KEY, booking_id TEXT NOT NULL, notification_type TEXT NOT NULL DEFAULT 'new_booking',
                        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed')), attempts INTEGER NOT NULL DEFAULT 0,
                        next_attempt_at TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, sent_at TEXT,
                        UNIQUE(booking_id, notification_type), FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
                    )"""
                )
                if _table_exists(conn, "notification_outbox_v2"):
                    conn.execute("INSERT INTO notification_outbox SELECT * FROM notification_outbox_v2")
                    conn.execute("DROP TABLE notification_outbox_v2")
                conn.execute("DROP TABLE bookings_v2")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.execute("PRAGMA foreign_keys=ON")

        conn.executescript(
            """
            BEGIN;
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                short_description TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                price_label TEXT NOT NULL DEFAULT '',
                duration_min INTEGER NOT NULL CHECK(duration_min > 0),
                icon TEXT NOT NULL DEFAULT '',
                color_enabled INTEGER NOT NULL DEFAULT 0 CHECK(color_enabled IN (0,1)),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nail_colors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                hex_color TEXT NOT NULL DEFAULT '#B9B2AA',
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS opening_hours (
                weekday INTEGER PRIMARY KEY CHECK(weekday BETWEEN 0 AND 6),
                enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                slot_interval_min INTEGER NOT NULL DEFAULT 30 CHECK(slot_interval_min BETWEEN 5 AND 240)
            );
            CREATE TABLE IF NOT EXISTS availability_overrides (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'available' CHECK(kind IN ('available','closed')),
                start_time TEXT NOT NULL DEFAULT '',
                end_time TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                public_code TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                customer_email TEXT NOT NULL DEFAULT '',
                customer_phone TEXT NOT NULL DEFAULT '',
                service_id TEXT NOT NULL,
                service_name TEXT NOT NULL,
                price_label TEXT NOT NULL DEFAULT '',
                nail_color_id TEXT NOT NULL DEFAULT '',
                nail_color_name TEXT NOT NULL DEFAULT '',
                nail_color_hex TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'confirmed' CHECK(status IN ('confirmed','requested','cancelled','rejected')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(service_id) REFERENCES services(id) ON UPDATE CASCADE
            );
            CREATE TABLE IF NOT EXISTS notification_outbox (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                notification_type TEXT NOT NULL DEFAULT 'new_booking',
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','failed')),
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT NOT NULL,
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sent_at TEXT,
                UNIQUE(booking_id, notification_type),
                FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_bookings_date ON bookings(date, start_time);
            CREATE INDEX IF NOT EXISTS idx_bookings_code ON bookings(public_code);
            CREATE INDEX IF NOT EXISTS idx_outbox_due ON notification_outbox(status, next_attempt_at);
            CREATE INDEX IF NOT EXISTS idx_availability_overrides_date ON availability_overrides(date, kind, start_time);
            COMMIT;
            """
        )

        # Explicit migrations for databases created by v1.
        if not _column_exists(conn, "services", "color_enabled"):
            conn.execute("ALTER TABLE services ADD COLUMN color_enabled INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE services SET color_enabled=1 WHERE id IN ('hands','feet','hands-foot-massage','hands-feet')")
        for column in ("nail_color_id", "nail_color_name", "nail_color_hex"):
            if not _column_exists(conn, "bookings", column):
                conn.execute(f"ALTER TABLE bookings ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")

        _seed_defaults(conn)
        conn.execute(
            "INSERT INTO meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )


def backup_database(db_path: Path, backups_dir: Path, backup_keep: int, reason: str) -> Path | None:
    if not db_path.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backups_dir / f"chez-philipp-{reason}-{stamp}.sqlite"
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(dest)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    rotate_backups(backups_dir, backup_keep)
    return dest


def rotate_backups(backups_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    files = sorted(backups_dir.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)


def rows(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def export_payload(conn: sqlite3.Connection) -> dict:
    return {
        "format": "chez-philipp-backup",
        "version": BACKUP_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "data": {
            "services": rows(conn, "SELECT * FROM services ORDER BY sort_order, name"),
            "nail_colors": rows(conn, "SELECT * FROM nail_colors ORDER BY sort_order, name"),
            "opening_hours": rows(conn, "SELECT * FROM opening_hours ORDER BY weekday"),
            "availability_overrides": rows(conn, "SELECT * FROM availability_overrides ORDER BY date, start_time"),
            "bookings": rows(conn, "SELECT * FROM bookings ORDER BY date, start_time"),
            "meta": {r["key"]: r["value"] for r in rows(conn, "SELECT key,value FROM meta") if r["key"] != "schema_version"},
        },
    }


def validate_backup(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("format") != "chez-philipp-backup":
        raise ValueError("Unbekanntes Backup-Format")
    version = payload.get("version")
    if version not in {1, 2, 3}:
        raise ValueError("Nicht unterstützte Backup-Version")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("Backup enthält keinen gültigen Datenbereich")
    services = data.get("services", [])
    colors = data.get("nail_colors", []) if version >= 2 else []
    hours = data.get("opening_hours", [])
    overrides = data.get("availability_overrides", []) if version >= 3 else []
    bookings = data.get("bookings", [])
    if not all(isinstance(x, list) for x in (services, colors, hours, overrides, bookings)):
        raise ValueError("Backup-Daten sind beschädigt")
    return {
        "version": version,
        "services": len(services),
        "nail_colors": len(colors),
        "opening_hours": len(hours),
        "availability_overrides": len(overrides),
        "bookings": len(bookings),
    }
