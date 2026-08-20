# Chez Philipp – Docker v4.0.0

Chez Philipp ist eine iPhone-first Buchungs-PWA für den privaten Betrieb. Docker v4.0.0 und Pages v4.0.0 gehören zum selben Release. Das Docker-Paket ist vollständig eigenständig: Flask-Backend, REST-API, SQLite, PWA, Adminbereich, Backup/Restore und Benachrichtigungen laufen in einem Container. Das Pages-Paket ist nur ein zusätzlicher statischer Client.

## Neu in v4

v4 führt zwei bewusst getrennte Terminwege ein:

1. **Termin buchen** – die Benutzerin wählt einen von Philipp freigegebenen Slot. Dieser Termin wird sofort als `confirmed` gespeichert und blockiert den Zeitraum.
2. **Freien Termin anfragen** – Datum und Uhrzeit werden frei per iOS-Date-/Time-Picker vorgeschlagen. Die Anfrage wird als `requested` gespeichert und blockiert noch keinen Zeitraum. Im Adminbereich kann Philipp sie bestätigen oder ablehnen. Vor einer Bestätigung wird erneut auf Konflikte mit bereits bestätigten Terminen geprüft.

Die Verfügbarkeit besteht aus:

- einem **regelmässigen Wochenplan** als Grundregel,
- **Tagesausnahmen**, die die Wochenregel für ein konkretes Datum ersetzen,
- mehreren freien Zeitfenstern am selben Ausnahmetag,
- der Möglichkeit, einen einzelnen Tag vollständig zu sperren.

Beispiel: Samstag ist regulär 09:00–16:00 verfügbar. Für einen bestimmten Samstag können stattdessen 10:00–13:00 und 15:00–18:00 freigegeben werden. Ein sonst geschlossener Mittwoch kann einmalig 19:00–21:30 freigegeben werden.

## Benachrichtigungen

Neue Server-Buchungen und freie Terminanfragen erzeugen eine persistente Outbox-Nachricht. Ein SMTP-Fehler macht die Buchung/Anfrage nicht rückgängig; die Zustellung wird mit exponentiellem Abstand erneut versucht.

- **Direkte Buchung:** HTML-Mail + Text-Fallback + `.ics`-Anhang.
- **Freie Terminanfrage:** HTML-Mail + Text-Fallback, bewusst **ohne ICS**, weil der Termin noch nicht bestätigt ist.
- Keine Bestätigungs- oder Storno-Mail an die buchende Person.
- Keine Secrets in JSON-Backups.

### Gmail mit App-Passwort

```env
NOTIFY_ENABLED=true
NOTIFY_EMAIL=deine-zieladresse@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_USER=chezphilipp.notifications@gmail.com
SMTP_PASSWORD=DEIN_16_STELLIGES_APP_PASSWORT
SMTP_FROM=chezphilipp.notifications@gmail.com
NOTIFY_RETRY_SECONDS=60
NOTIFY_MAX_ATTEMPTS=12
```

Das Google-App-Passwort ohne Leerzeichen eintragen. Das normale Google-Passwort gehört nicht in den Container.

## Portainer Stack Web Editor

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
      APP_URL: "https://chezphilipp.example.com"
      APP_TIMEZONE: "Europe/Zurich"
      AUTH_ENABLED: "true"
      ADMIN_PIN: "${ADMIN_PIN}"
      SECRET_KEY: "${SECRET_KEY}"
      BACKUP_KEEP: "50"
      BOOKING_CUSTOMER_NAME: "Meine Frau"
      PWA_ALLOWED_ORIGIN: "https://app.example.com"
      NOTIFY_ENABLED: "true"
      NOTIFY_EMAIL: "${NOTIFY_EMAIL}"
      SMTP_HOST: "smtp.gmail.com"
      SMTP_PORT: "465"
      SMTP_SECURITY: "ssl"
      SMTP_USER: "${SMTP_USER}"
      SMTP_PASSWORD: "${SMTP_PASSWORD}"
      SMTP_FROM: "${SMTP_USER}"
      NOTIFY_RETRY_SECONDS: "60"
      NOTIFY_MAX_ATTEMPTS: "12"
    restart: unless-stopped
```

Für reinen Heimnetz-Dockerbetrieb kann `PWA_ALLOWED_ORIGIN` leer bleiben. Wenn die Pages-PWA verwendet wird, muss dort exakt deren HTTPS-Origin stehen.

## Heimnetz / Pi-hole / eigene Domain

Empfohlenes Setup:

```text
iPhone
  ↓
https://chezphilipp.deinedomain.ch
  ↓
Pi-hole Split-DNS
  ↓
IP des Docker-Servers
  ↓
Reverse Proxy :443
  ↓
chez-philipp :8080
```

Keine Portweiterleitung auf dem Internet-Router ist notwendig. Ein gültiges Zertifikat kann über eine DNS-01-Challenge der eigenen Cloudflare-Domain bezogen werden.

## Datenmodell

SQLite liegt unter `/app/data/app.sqlite` und verwendet WAL, `synchronous=FULL` und Foreign Keys.

Wichtige Tabellen:

- `services`
- `nail_colors`
- `opening_hours` – regelmässiger Wochenplan
- `availability_overrides` – konkrete Tagesfreigaben / gesperrte Tage
- `bookings` – direkte Buchungen und Anfragen
- `notification_outbox`
- `meta`

Buchungsstatus:

- `confirmed` – verbindlicher Termin, blockiert den Zeitraum
- `requested` – freie Anfrage, blockiert nicht
- `cancelled` – stornierter bestätigter Termin
- `rejected` – abgelehnte Anfrage

## Verfügbarkeitslogik

Für einen Tag gilt:

1. Existieren Tagesausnahmen, ersetzen sie die Wochenregel vollständig.
2. Eine `closed`-Ausnahme sperrt den Tag.
3. `available`-Ausnahmen bilden die freigegebenen Zeitfenster.
4. Ohne Tagesausnahme gilt der normale Wochenplan.
5. Die Dauer der gewählten Leistung muss vollständig in ein freigegebenes Fenster passen.
6. Bestätigte Termine werden als belegt abgezogen.
7. Offene Anfragen blockieren keine Slots.

## Adminbereich

Der Adminbereich enthält:

- **Freizeit:** Wochenplan + Tagesausnahmen
- **Leistungen:** Name, Dauer, Preistext, Aktivstatus, Farbauswahl
- **Farben:** Name, Hex-Farbe, Reihenfolge, Aktivstatus
- **Termine:** bestätigte Termine, offene Anfragen, Mailstatus, Bestätigen/Ablehnen, Stornieren, Mail-Retry
- **Backup:** JSON und serverseitiger SQLite-Snapshot

## Backup / Restore / Migration

Backupformat v3:

```json
{
  "format": "chez-philipp-backup",
  "version": 3,
  "data": {
    "services": [],
    "nail_colors": [],
    "opening_hours": [],
    "availability_overrides": [],
    "bookings": [],
    "meta": {}
  }
}
```

v1- und v2-Backups bleiben importierbar. Beim Upgrade einer bestehenden v1- oder v2-Datenbank auf Schema v3 wird zuerst automatisch ein SQLite-Snapshot unter `/app/data/backups/` angelegt. Danach wird die Buchungstabelle kontrolliert erweitert, sodass die neuen Status `requested` und `rejected` unterstützt werden. Bestehende Termine und Outbox-Einträge bleiben erhalten.

Vor destruktiven Imports wird ebenfalls ein Sicherheitsbackup erstellt.

## Pages / Local Provider

Die statische Pages-PWA verwendet dieselbe UI-Logik und bietet weiterhin:

- Server Provider → Docker REST API
- Local Provider → IndexedDB

Im lokalen Modus existieren Wochenplan, Tagesausnahmen, Buchungen und Anfragen ebenfalls. Lokale Buchungen/Anfragen senden bewusst keine E-Mail.

## Offline-App-Shell und Updates

Cache-Version v4: `chez-philipp-pwa-v4`.

Die App-Shell enthält HTML, CSS, JavaScript, Manifest, Offline-Seite und lokale Icons. Es gibt keine externen CDN-Abhängigkeiten. Neue Service-Worker-Versionen werden heruntergeladen und warten, bis die App sicher neu gestartet oder ein manuelles Update ausgelöst wird. Ein `controllerchange` löst nur nach einer bewussten Update-Aktion genau einen Reload aus.

IndexedDB- und SQLite-Daten werden durch Frontend-Updates nicht gelöscht.

## ZIP-Workflow

Das Repository enthält `.github/workflows/import-zip.yml`. Ein neu hochgeladenes `*.zip` wird nur verarbeitet, wenn genau ein ZIP eindeutig vorhanden ist. `.git` und der Workflow selbst werden geschützt, Altdateien werden kontrolliert ersetzt und das ZIP nach erfolgreichem Import entfernt.

Das Release-ZIP repräsentiert direkt das Repository-Root und enthält keine zusätzliche Verzeichnisebene.

## Versionskompatibilität

- Docker: `4.0.0`
- Pages: `4.0.0`
- SQLite Schema: `3`
- JSON Backup: `3`
- IndexedDB Schema: `3`
- Service Worker Cache: `chez-philipp-pwa-v4`

## Tests / bekannte Einschränkungen

Statisch geprüft werden Python-Syntax, JavaScript-Syntax, Datenbankschema, v1/v2→v3-Migration, Backupformat, Service-Worker-Dateien und ZIP-Struktur. Ein echter Gmail-Versand benötigt reale Zugangsdaten. Ein vollständiger iOS-PWA-Lifecycle kann nur auf einem echten iPhone/Safari abschliessend geprüft werden.
