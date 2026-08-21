from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 4
BACKUP_VERSION = 3

DEFAULT_SERVICES = [
    {
        "id": "hands",
        "name": "Händchen hübsch",
        "short_description": "Nägel Hände · klein, fein, frisch",
        "description": "15 Minuten für Feile, Farbe und das kleine frisch-gemacht-Gefühl.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "HH",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 10,
    },
    {
        "id": "feet",
        "name": "Zehenzauber",
        "short_description": "Nägel Füsse · kurzer Boxenstopp",
        "description": "Kurzer Boxenstopp für die Zehen – Farbe drauf, Alltag aus.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "ZZ",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 20,
    },
    {
        "id": "hands-feet",
        "name": "Doppelglanz",
        "short_description": "Nägel Hände & Füsse · alles in einem",
        "description": "Hände und Füsse im Doppelpack, damit am Ende einfach alles zusammenpasst.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "DG",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 30,
    },
    {
        "id": "footpack-hands",
        "name": "Päckli & Pfötchen",
        "short_description": "Fusspackung + Nägel Hände",
        "description": "Während die Füsse gemütlich eingepackt sind, bekommen die Hände ihren frischen Glanz.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "PP",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 40,
    },
    {
        "id": "footpack-feet",
        "name": "Päckli & Pedi",
        "short_description": "Fusspackung + Nägel Füsse",
        "description": "Pflegepackung für die Füsse plus frische Farbe auf den Nägeln – effizient gemütlich.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "PF",
        "color_enabled": 1,
        "active": 1,
        "sort_order": 50,
    },
    {
        "id": "footpack",
        "name": "Füsse im Päckli",
        "short_description": "Fusspackung · Füsse hoch",
        "description": "Fusspackung drauf, Füsse hoch und 15 Minuten einfach einmal nichts müssen.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "FP",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 60,
    },
    {
        "id": "foot-massage",
        "name": "Sohle Mio",
        "short_description": "Fussmassage · Feierabend für die Füsse",
        "description": "15 Minuten Kneten gegen müde Füsse – Hausservice mit Lieblingsmensch-Faktor.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "SM",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 70,
    },
    {
        "id": "bubble-bath",
        "name": "Schaumkrönung",
        "short_description": "Schaumbad · warm, ruhig, fertig",
        "description": "30 Minuten warmes Schaumbad – kein Termin, kein Telefon, nur Schaum und Ruhe.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "SK",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 80,
    },
    {
        "id": "hand-massage",
        "name": "Handkuss",
        "short_description": "Handmassage · kleine Pause",
        "description": "Kurze Handmassage für Hände, die heute schon genug getan haben.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "HK",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 90,
    },
    {
        "id": "head-massage",
        "name": "Kopf aus, Hände an",
        "short_description": "Kopf- & Schläfenmassage",
        "description": "15 Minuten Schläfen- und Kopfmassage für den schnellen Feierabend im Kopf.",
        "price_label": "1 Küsschen",
        "duration_min": 15,
        "icon": "KA",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 100,
    },
    {
        "id": "back-massage",
        "name": "Rücken frei",
        "short_description": "Rückenmassage · Alltag raus",
        "description": "30 Minuten Rückenmassage – genau da, wo der Tag noch sitzt.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "RF",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 110,
    },
    {
        "id": "face-mask",
        "name": "Glow-Zeit",
        "short_description": "Gesichtsmaske · Ruhemodus an",
        "description": "Gesichtsmaske und Ruhemodus – 30 Minuten kleine Wellness-Insel zuhause.",
        "price_label": "2 Küsschen",
        "duration_min": 30,
        "icon": "GZ",
        "color_enabled": 0,
        "active": 1,
        "sort_order": 120,
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
    0: {"enabled": 1, "start_time": "19:00", "end_time": "22:00", "slot_interval_min": 15},
    1: {"enabled": 1, "start_time": "19:00", "end_time": "22:00", "slot_interval_min": 15},
    2: {"enabled": 1, "start_time": "19:00", "end_time": "22:00", "slot_interval_min": 15},
    3: {"enabled": 1, "start_time": "19:00", "end_time": "22:00", "slot_interval_min": 15},
    4: {"enabled": 1, "start_time": "19:00", "end_time": "22:00", "slot_interval_min": 15},
    5: {"enabled": 1, "start_time": "09:00", "end_time": "23:00", "slot_interval_min": 15},
    6: {"enabled": 1, "start_time": "09:00", "end_time": "23:00", "slot_interval_min": 15},
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


def _migrate_v6_defaults(conn: sqlite3.Connection, existing_version: int) -> None:
    """Adopt v6 Chez-Philipp defaults only when the old defaults are still untouched.

    Custom services and custom availability remain intact. Known untouched v5 seed
    services are refreshed/deactivated, while the new catalog entries are inserted.
    """
    if not existing_version or existing_version >= 4:
        return

    now = datetime.now().isoformat(timespec="seconds")
    old_hours = {
        0: (1, "09:00", "18:00", 30),
        1: (1, "09:00", "18:00", 30),
        2: (1, "09:00", "18:00", 30),
        3: (1, "09:00", "18:00", 30),
        4: (1, "09:00", "18:00", 30),
        5: (0, "09:00", "16:00", 30),
        6: (0, "09:00", "16:00", 30),
    }
    current_hours = {
        int(r["weekday"]): (int(r["enabled"]), r["start_time"], r["end_time"], int(r["slot_interval_min"]))
        for r in conn.execute("SELECT * FROM opening_hours ORDER BY weekday").fetchall()
    }
    if current_hours == old_hours:
        for day, values in DEFAULT_HOURS.items():
            conn.execute(
                "UPDATE opening_hours SET enabled=?,start_time=?,end_time=?,slot_interval_min=? WHERE weekday=?",
                (values["enabled"], values["start_time"], values["end_time"], values["slot_interval_min"], day),
            )

    old_seed = {
        "hands": ("Signature Manicure", 45),
        "feet": ("Signature Pedicure", 45),
        "hands-foot-massage": ("Manicure & Foot Ritual", 75),
        "hands-feet": ("Full Care Ritual", 90),
        "foot-massage": ("Foot Massage", 30),
        "philipp-exclusive": ("Philipp's Private Ritual", 60),
    }
    new_by_id = {item["id"]: item for item in DEFAULT_SERVICES}

    for service_id, (old_name, old_duration) in old_seed.items():
        row = conn.execute("SELECT name,duration_min FROM services WHERE id=?", (service_id,)).fetchone()
        if not row or row["name"] != old_name or int(row["duration_min"]) != old_duration:
            continue
        replacement = new_by_id.get(service_id)
        if replacement:
            conn.execute(
                """UPDATE services SET name=?,short_description=?,description=?,price_label=?,duration_min=?,icon=?,
                   color_enabled=?,active=?,sort_order=?,updated_at=? WHERE id=?""",
                (replacement["name"], replacement["short_description"], replacement["description"],
                 replacement["price_label"], replacement["duration_min"], replacement["icon"],
                 replacement["color_enabled"], replacement["active"], replacement["sort_order"], now, service_id),
            )
        else:
            conn.execute("UPDATE services SET active=0,updated_at=? WHERE id=?", (now, service_id))

    for service in DEFAULT_SERVICES:
        conn.execute(
            """INSERT INTO services
            (id,name,short_description,description,price_label,duration_min,icon,color_enabled,active,sort_order,created_at,updated_at)
            VALUES (:id,:name,:short_description,:description,:price_label,:duration_min,:icon,:color_enabled,:active,:sort_order,:created_at,:updated_at)
            ON CONFLICT(id) DO NOTHING""",
            {**service, "created_at": now, "updated_at": now},
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
        _migrate_v6_defaults(conn, existing_version)
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
