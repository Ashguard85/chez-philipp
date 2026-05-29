# 💅 Chez Philipp – Buchungsplattform + CalDAV Kalender

## 🏗️ Stack
- **App** (nginx) → Port 3200
- **Radicale** (CalDAV Kalender) → Port 5232

---

## 🚀 Starten

```bash
# 1. Passwort setzen in docker-compose.yml:
#    RADICALE_PASSWORD=DEIN_PASSWORT
#    (auch in frontend/index.html anpassen: CALDAV_PASS)

# 2. Starten:
docker compose up -d

# 3. App:
http://SERVER-IP:3200
```

---

## 📱 iPhone Kalender einrichten (einmalig)

**Einstellungen → Kalender → Accounts → Account hinzufügen → Andere → CalDAV-Account**

| Feld     | Wert                              |
|----------|-----------------------------------|
| Server   | `http://SERVER-IP:5232`           |
| Benutzer | `philipp`                         |
| Passwort | dein Passwort aus docker-compose  |
| Beschr.  | Chez Philipp                      |

→ Speichern. Ab jetzt erscheinen alle Buchungen automatisch im iPhone Kalender! 🗓️

---

## ⚙️ Passwort ändern

In `docker-compose.yml`:
```yaml
environment:
  - RADICALE_USER=philipp
  - RADICALE_PASSWORD=NEUES_PASSWORT
```

Dasselbe Passwort auch in `frontend/index.html` bei `CALDAV_PASS` eintragen.

Dann neu deployen:
```bash
docker compose down && docker compose up -d --build
```

---

## 🛑 Stoppen
```bash
docker compose down
```

Kalender-Daten bleiben im Volume `radicale-data` erhalten.
