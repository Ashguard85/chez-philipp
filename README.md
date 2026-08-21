# Chez Philipp – Docker v7.0.0

Chez Philipp ist eine iPhone-first Buchungs-PWA für den privaten Betrieb zuhause. Docker v7.0.0 und Pages v7.0.0 gehören zum selben Release. Das Docker-Paket ist vollständig eigenständig: Flask-Backend, REST-API, SQLite, PWA, Adminbereich, Backup/Restore, Gmail/SMTP-Benachrichtigungen und privater Kalender-Feed laufen in einem Container.

## Neu in v7

v7 ergänzt im Adminbereich echte, dauerhafte Löschfunktionen. **Deaktivieren/Stornieren** bleibt weiterhin verfügbar, wenn Daten nur ausgeblendet bzw. historisch markiert werden sollen.

- **Termine/Anfragen endgültig löschen:** entfernt den Datensatz vollständig aus SQLite/IndexedDB. Zugehörige Outbox-Einträge werden auf dem Server ebenfalls entfernt; bestätigte Termine verschwinden dadurch aus dem privaten Kalender-Feed.
- **Behandlungen endgültig löschen:** entfernt die Behandlung vollständig aus dem Katalog. Bestehende historische Buchungen bleiben lesbar, weil der beim Buchen gespeicherte Name und Preistext erhalten bleiben.
- **Farben endgültig löschen:** entfernt die Farbe vollständig aus dem Katalog. Historische Buchungen behalten den gespeicherten Farbnamen und Farbwert.
- Jede dauerhafte Löschung verlangt eine ausdrückliche Bestätigung in der Oberfläche.

## Standard-Freizeit und Leistungen

Die in v6 eingeführten privaten Chez-Philipp-Defaults bleiben unverändert.

### Standard-Freizeit

- Montag–Freitag: **19:00–22:00**, Startzeiten im **15-Minuten-Takt**
- Samstag–Sonntag: **09:00–23:00**, Startzeiten im **15-Minuten-Takt**

Die Dauer einer Leistung muss vollständig in das freie Fenster passen. Eine 30-Minuten-Leistung kann werktags daher spätestens um 21:30 starten; eine 15-Minuten-Leistung spätestens um 21:45.

### Standard-Leistungen

| Leistung | Inhalt | Dauer |
| --- | --- | ---: |
| Händchen hübsch | Nägel Hände | 15 Min. |
| Zehenzauber | Nägel Füsse | 15 Min. |
| Doppelglanz | Nägel Hände & Füsse | 30 Min. |
| Päckli & Pfötchen | Fusspackung + Nägel Hände | 30 Min. |
| Päckli & Pedi | Fusspackung + Nägel Füsse | 30 Min. |
| Füsse im Päckli | Fusspackung | 15 Min. |
| Sohle Mio | Fussmassage | 15 Min. |
| Schaumkrönung | Schaumbad | 30 Min. |
| Handkuss | Handmassage | 15 Min. |
| Kopf aus, Hände an | Kopf-/Schläfenmassage | 15 Min. |
| Rücken frei | Rückenmassage | 30 Min. |
| Glow-Zeit | Gesichtsmaske | 30 Min. |

Nagel-Leistungen verwenden weiterhin die administrierbare Farbauswahl. 15-Minuten-Leistungen tragen standardmässig den privaten Preistext `1 Küsschen`, 30-Minuten-Leistungen `2 Küsschen`; alles bleibt im Adminbereich editierbar.

Beim Upgrade werden die v6-Defaults nur automatisch übernommen, wenn der alte v5-Standard noch unverändert vorhanden ist. Bereits individuell angepasste Wochenzeiten oder Leistungen werden nicht still überschrieben. Alte Standard-Leistungen, die v6 nicht mehr verwendet, werden bei einem unveränderten v5-Katalog deaktiviert statt gelöscht, damit bestehende Buchungen referenziell intakt bleiben.

## Terminwege

1. **Termin buchen** – die Benutzerin wählt einen freigegebenen Slot. Dieser Termin wird sofort als `confirmed` gespeichert und blockiert den Zeitraum.
2. **Freien Termin anfragen** – Datum und Uhrzeit werden frei per iOS-Date-/Time-Picker vorgeschlagen. Die Anfrage wird als `requested` gespeichert und blockiert noch keinen Zeitraum. Im Adminbereich kann sie bestätigt oder abgelehnt werden. Vor einer Bestätigung wird erneut auf Konflikte geprüft.

Die Verfügbarkeit besteht aus einem regelmässigen Wochenplan sowie beliebigen Tagesausnahmen. Tagesausnahmen ersetzen die Wochenregel für das konkrete Datum und können mehrere freie Fenster oder einen vollständig gesperrten Tag enthalten.

## Benachrichtigungen

Neue Server-Buchungen und freie Terminanfragen erzeugen eine persistente Outbox-Nachricht. Ein SMTP-Fehler macht den Termin nicht rückgängig; die Zustellung wird automatisch erneut versucht.

- Direkte Buchung: HTML-Mail + Text-Fallback + `.ics` mit `STATUS:CONFIRMED`
- Freie Terminanfrage: HTML-Mail + Text-Fallback + `.ics` mit `STATUS:TENTATIVE`
- Privater Kalender-Feed: ausschliesslich bestätigte Termine
- Keine Bestätigungs- oder Storno-Mail an die buchende Person
- Keine SMTP-Secrets oder Kalender-Token in JSON-Backups

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
      CALENDAR_FEED_TOKEN: "${CALENDAR_FEED_TOKEN}"
      PWA_ALLOWED_ORIGIN: ""
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

Für reinen Heimnetz-Dockerbetrieb kann `PWA_ALLOWED_ORIGIN` leer bleiben.

## Heimnetz / Pi-hole / eigene Domain

Empfohlen: `https://chezphilipp.deinedomain.ch` wird im Heimnetz per Pi-hole Split-DNS auf die IP des Docker-/Reverse-Proxy-Servers aufgelöst. Es ist keine Portweiterleitung auf der Swisscom Internet-Box notwendig. Ein öffentlich gültiges Zertifikat kann per DNS-01-Challenge über Cloudflare ausgestellt werden.

## Privater Kalender-Feed

Setze in Portainer einen langen zufälligen Token:

```env
CALENDAR_FEED_TOKEN=HIER_EINEN_LANGEN_ZUFAELLIGEN_TOKEN_EINTRAGEN
```

Der Adminbereich zeigt die Abonnement-URL auf Basis von `APP_URL`, z. B. `https://chezphilipp.deinedomain.ch/calendar.ics?token=...`. Der Feed enthält nur `confirmed`-Termine, verwendet stabile UIDs und liefert `Cache-Control: private, no-store`. Zum Widerrufen den Token ändern und den Stack neu deployen.

## Datenmodell

SQLite liegt unter `/app/data/app.sqlite` und verwendet WAL, `synchronous=FULL` und Foreign Keys. Wichtige Tabellen: `services`, `nail_colors`, `opening_hours`, `availability_overrides`, `bookings`, `notification_outbox`, `meta`.

Buchungsstatus: `confirmed`, `requested`, `cancelled`, `rejected`.

## Backup / Restore / Migration

JSON-Backupformat bleibt v3. v1-, v2- und v3-Backups bleiben importierbar. Vor Datenbankmigrationen und destruktiven Imports wird automatisch ein SQLite-Snapshot unter `/app/data/backups/` angelegt.

v7 verwendet SQLite-Schema 5. Bei der Migration wird die starre Fremdschlüsselbindung zwischen historischen Buchungen und dem Leistungskatalog gelöst. Die Buchung behält ihre gespeicherten Snapshots, sodass eine Behandlung später wirklich gelöscht werden kann. Vor der Migration wird wie bisher automatisch ein SQLite-Snapshot angelegt. Das JSON-Backupformat bleibt v3.

## Pages / Local Provider

Die statische Pages-PWA verwendet dieselbe UI-Logik und bietet Server Provider → Docker REST API sowie Local Provider → IndexedDB. Im lokalen Modus existieren Wochenplan, Tagesausnahmen, Buchungen und Anfragen ebenfalls; lokale Buchungen senden bewusst keine E-Mail.

## Offline-App-Shell und Updates

Cache-Version v7: `chez-philipp-pwa-v7`. Die App-Shell enthält HTML, CSS, JavaScript, Manifest, Offline-Seite und lokale Icons. Es gibt keine externen CDN-Abhängigkeiten. Neue Service-Worker-Versionen werden vorbereitet und nicht mitten in einer laufenden Sitzung erzwungen.

## ZIP-Workflow

`.github/workflows/import-zip.yml` verarbeitet genau ein neu hochgeladenes ZIP, schützt `.git` und den Workflow selbst, ersetzt die Repository-Dateien kontrolliert und entfernt das ZIP nach erfolgreichem Import. Das Release-ZIP repräsentiert direkt das Repository-Root.

## Versionskompatibilität

- Docker: `7.0.0`
- Pages: `7.0.0`
- SQLite Schema: `5`
- JSON Backup: `3`
- IndexedDB Datenmigration: `4`
- IndexedDB Object-Store-Version: `3`
- Service Worker Cache: `chez-philipp-pwa-v7`

## Tests / bekannte Einschränkungen

Geprüft werden Python- und JavaScript-Syntax, frische SQLite-Initialisierung, v6→v7-Datenbankmigration, Hard-Delete von Termin/Behandlung/Farbe mit Erhalt historischer Snapshots, Slot-Berechnung, Backupformat, Service Worker, Docker-/Pages-Codegleichheit und ZIP-Struktur. Ein echter Gmail-Versand benötigt reale Zugangsdaten; ein vollständiger iOS-PWA-Lifecycle kann nur auf einem echten iPhone abschliessend geprüft werden.
