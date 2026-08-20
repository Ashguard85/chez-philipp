# Chez Philipp – Docker v2.0.0

Vollständige self-hosted Fullstack-Anwendung für das private Buchungstool **Chez Philipp**. Das Docker-Paket funktioniert eigenständig und liefert Flask-Backend, REST-API, SQLite-Datenbank, vollständiges Frontend und PWA aus einem Container aus. Persistente Nutzdaten liegen ausschließlich unter `/app/data`.

Docker v2.0.0 und Pages v2.0.0 gehören zum selben Release. Das gemeinsame JSON-Backupformat ist Version 2; v1-Backups können weiterhin importiert werden.

## Architektur

```text
Docker Browser/PWA
      │
      ▼
Flask + gemeinsame Frontend-Codebasis
      │
      ├── REST API
      ├── SQLite /app/data/app.sqlite
      ├── Mail-Outbox
      └── Backups /app/data/backups

GitHub-Pages-PWA (optional)
      ├── ServerProvider -> Docker REST API
      └── LocalProvider  -> IndexedDB
```

Die GitHub-Pages-PWA ist niemals Voraussetzung für den Docker-Betrieb.

## v2 – neue Buchungsbenachrichtigung

Bei **jeder neu angelegten Server-Buchung** kann der Docker-Server eine E-Mail an Philipp senden. Es werden bewusst **keine** Bestätigungs- oder Storno-Mails an den buchenden Benutzer versendet.

Die Buchung und der Benachrichtigungsauftrag werden persistent gespeichert. Ein SMTP-Fehler macht die Buchung nicht rückgängig. Fehlgeschlagene Nachrichten bleiben in `notification_outbox` erhalten und werden mit wachsendem Abstand erneut versucht. Beim Neustart bleibt der Auftrag erhalten. Im Adminbereich wird der Zustellstatus angezeigt und ein manueller Retry angeboten.

Der lokale IndexedDB-Modus kann keine Server-E-Mail auslösen. Für den gewünschten Heimnetz-Betrieb mit Benachrichtigung daher das Docker-Frontend bzw. den Pages-**Server-Modus** verwenden.

### Gmail

Für ein privates Setup kann Gmail direkt per SMTP verwendet werden:

```env
NOTIFY_ENABLED=true
NOTIFY_EMAIL=zieladresse@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=absender@gmail.com
SMTP_PASSWORD=GOOGLE_APP_PASSWORT
SMTP_FROM=absender@gmail.com
NOTIFY_RETRY_SECONDS=60
NOTIFY_MAX_ATTEMPTS=12
```

`SMTP_PASSWORD` gehört ausschließlich in Portainer/Docker-Environment und niemals ins Repository. Für klassische SMTP-Anmeldung mit einem Google-Konto wird ein Google-App-Passwort verwendet; das normale Kontopasswort soll nicht hinterlegt werden. Falls das Google-Konto keine App-Passwörter zulässt, kann stattdessen ein anderer SMTP-Anbieter verwendet werden.

Die Mail enthält nur die Informationen zur neuen Buchung, z. B. Termin, Behandlung, gewählte Nagelfarbe, Name, Buchungscode und optional Telefon/E-Mail/Notiz.

## Nagelfarben

v2 ergänzt eine administrierbare Farbpalette. Jede Leistung besitzt die Option **„Farbauswahl bei dieser Leistung anzeigen“**. Standardmäßig ist sie bei Manicure/Pedicure-bezogenen Leistungen aktiv.

Farben besitzen:

- ID
- Name
- Hex-Farbwert
- Aktiv-Status
- Sortierreihenfolge

Standardpalette: Nude, Blush, Rosé, Classic Red, Bordeaux, Taupe, Milky White, Black, French und „Vor Ort entscheiden“.

Eine Buchung speichert zusätzlich einen Snapshot aus `nail_color_id`, `nail_color_name` und `nail_color_hex`. Alte Buchungen bleiben dadurch verständlich, selbst wenn die Palette später geändert wird.

## Datenbank / Migration

SQLite: `/app/data/app.sqlite`

Die Verbindung verwendet:

- WAL
- `synchronous=FULL`
- `foreign_keys=ON`
- Busy Timeout

Schema v2 ergänzt:

- `services.color_enabled`
- Tabelle `nail_colors`
- Farbsnapshot-Felder in `bookings`
- persistente `notification_outbox`

Beim Update einer bestehenden v1-Datenbank wird vor der Migration automatisch ein SQLite-Snapshot unter `/app/data/backups/` erzeugt. Bestehende Buchungen bleiben erhalten.

## Portainer / Git Deployment

Beispiel:

```yaml
services:
  app:
    build:
      context: https://github.com/USER/chez-philipp-docker.git#main
    container_name: chez-philipp
    ports:
      - "8090:8080"
    volumes:
      - /home/USER/docker/chez-philipp/data:/app/data
    environment:
      APP_TITLE: "Chez Philipp"
      APP_URL: "https://chez-philipp.example.internal"
      APP_TIMEZONE: "Europe/Zurich"
      AUTH_ENABLED: "true"
      ADMIN_PIN: "${ADMIN_PIN}"
      SECRET_KEY: "${SECRET_KEY}"
      BACKUP_KEEP: "50"
      PWA_ALLOWED_ORIGIN: "https://app.example.com"

      NOTIFY_ENABLED: "true"
      NOTIFY_EMAIL: "${NOTIFY_EMAIL}"
      SMTP_HOST: "smtp.gmail.com"
      SMTP_PORT: "587"
      SMTP_SECURITY: "starttls"
      SMTP_USER: "${SMTP_USER}"
      SMTP_PASSWORD: "${SMTP_PASSWORD}"
      SMTP_FROM: "${SMTP_USER}"
      NOTIFY_RETRY_SECONDS: "60"
      NOTIFY_MAX_ATTEMPTS: "12"
    restart: unless-stopped
```

Für reinen Heimnetz-Betrieb muss Cloudflare nicht verwendet werden. Soll die App als installierte PWA funktionieren, sollte der Browser sie trotzdem über einen sicheren HTTPS-Ursprung erreichen. Das kann beispielsweise ein lokaler Reverse Proxy mit vertrauenswürdigem Zertifikat übernehmen.

## Environment-Variablen

| Variable | Zweck |
|---|---|
| `APP_TITLE` | Anzeigename |
| `APP_URL` | öffentliche bzw. kanonische Backend-Adresse |
| `APP_TIMEZONE` | Standard `Europe/Zurich` |
| `SECRET_KEY` | Flask Secret |
| `AUTH_ENABLED` | Admin-PIN-Prüfung aktivieren |
| `ADMIN_PIN` | Admin-PIN |
| `BACKUP_KEEP` | Anzahl SQLite-Sicherungsdateien |
| `PWA_ALLOWED_ORIGIN` | exakt erlaubte Pages-Origin für CORS |
| `NOTIFY_ENABLED` | Mailbenachrichtigung bei neuen Server-Buchungen |
| `NOTIFY_EMAIL` | Empfänger der Buchungsmail |
| `SMTP_HOST` | SMTP-Server |
| `SMTP_PORT` | SMTP-Port |
| `SMTP_SECURITY` | `starttls`, `ssl` oder `none` |
| `SMTP_USER` | SMTP-Benutzer |
| `SMTP_PASSWORD` | SMTP-/App-Passwort |
| `SMTP_FROM` | Absenderadresse |
| `SMTP_TIMEOUT` | SMTP-Timeout in Sekunden |
| `NOTIFY_RETRY_SECONDS` | Basisintervall für Retry |
| `NOTIFY_MAX_ATTEMPTS` | maximale automatische Versuche |

Keine Secrets hardcoden oder in JSON-Backups exportieren.

## API

Wichtige Endpunkte:

```text
GET  /health
GET  /api/config
GET  /api/services
GET  /api/nail-colors
GET  /api/availability
POST /api/bookings
GET  /api/bookings/by-code/<code>

GET  /api/admin/state
PUT  /api/admin/services
PUT  /api/admin/nail-colors
PUT  /api/admin/opening-hours
DELETE /api/admin/bookings/<id>
POST /api/admin/notifications/<booking-id>/retry
GET  /api/admin/export
POST /api/admin/import/preview
POST /api/admin/import/apply
GET  /api/admin/backup
```

Eine Stornierung erzeugt absichtlich keine E-Mail.

## CORS / Cloudflare

Falls das statische Pages-Frontend verwendet wird, darf CORS nicht auf `*` stehen. Setze die exakte Origin:

```env
PWA_ALLOWED_ORIGIN=https://app.example.com
```

Zugelassene Methoden: GET, POST, PUT, PATCH, DELETE, OPTIONS. Unterstützte zusätzliche Header umfassen `CF-Access-Client-Id`, `CF-Access-Client-Secret` und `X-Admin-Pin`.

Cloudflare ist für Chez Philipp im Heimnetz optional. Wenn es nicht verwendet wird, bleiben die Cloudflare-Felder im Pages-Setup leer.

## Backup / Restore

JSON-Format v2:

```json
{
  "format": "chez-philipp-backup",
  "version": 2,
  "data": {
    "services": [],
    "nail_colors": [],
    "opening_hours": [],
    "bookings": [],
    "meta": {}
  }
}
```

Die Mail-Outbox wird absichtlich **nicht** in das portable JSON-Backup aufgenommen, damit ein Restore keine alten Buchungsmails erneut versendet. Ein vollständiger SQLite-Snapshot enthält sie dagegen.

Vor serverseitigem Restore bzw. destruktivem Import wird automatisch ein SQLite-Sicherheitsbackup angelegt. v1-Backups bleiben importierbar; die v2-Farbpalette wird bei einem v1-Import nicht zerstört.

## PWA / Offline-App-Shell

Cache-Version v2: `chez-philipp-pwa-v2`.

App-Shell:

- `index.html`
- `app.js`
- `app.css`
- `config.js`
- Manifest
- Offline-Seite
- alle lokalen Icons

Keine externen Fonts/CDNs. Der Service Worker erzwingt keinen Reload mitten in einer Sitzung. Ein neues Release wird vorbereitet und erst nach sicherem Neustart oder bewusster Benutzeraktion aktiviert. Ein kontrollierter Reload erfolgt höchstens einmal.

## ZIP-Workflow

`.github/workflows/import-zip.yml` verarbeitet genau ein neu hochgeladenes `*.zip`, schützt `.git` sowie den Workflow selbst, lehnt unsichere Pfade/typische Secret-Dateien ab, entfernt alte Release-Dateien und das importierte ZIP und pusht den neuen Stand ohne Commit-Schleife.

Dieses ZIP bildet direkt das Root-Verzeichnis des Docker-Repositories ab.

## Bekannte Einschränkungen v2

- Keine bidirektionale Sync-Engine zwischen Local- und Server-Modus.
- Local-Modus kann keine E-Mail-Benachrichtigungen auslösen.
- Die SMTP-Outbox läuft bewusst im einzigen Gunicorn-Worker; die mitgelieferte Konfiguration verwendet deshalb `--workers 1`. Keine zusätzliche Queue/Microservice nötig.
- E-Mail-Zustellung kann von Gmail/SMTP/Internet abhängen; die persistente Outbox schützt vor einem einmaligen Zustellfehler, garantiert aber nicht die Annahme durch den externen Mailprovider.
- Für eine vollwertige installierte PWA auf iOS ist HTTPS erforderlich.
