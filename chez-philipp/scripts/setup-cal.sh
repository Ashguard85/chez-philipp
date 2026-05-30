#!/bin/sh
set -e
echo ">>> Chez Philipp CalDAV Setup..."

apk add --no-cache python3 py3-pip > /dev/null 2>&1
pip install bcrypt --quiet --break-system-packages > /dev/null 2>&1

# ── User anlegen ──
if [ ! -f /data/users ]; then
  echo ">>> Erstelle User: ${CALDAV_USER}"
  python3 -c "
import bcrypt, os
u = os.environ['CALDAV_USER']
p = os.environ['CALDAV_PASS']
h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
open('/data/users','w').write(f'{u}:{h}\n')
print('User erstellt:', u)
"
else
  echo ">>> User existiert bereits."
fi

# ── Radicale Config ──
mkdir -p /config
cat > /config/radicale.conf << CONF
[server]
hosts = 0.0.0.0:5232

[auth]
type = htpasswd
htpasswd_filename = /data/users
htpasswd_encryption = bcrypt

[storage]
filesystem_folder = /data/collections

[rights]
type = owner_only

[logging]
level = info

[headers]
Access-Control-Allow-Origin = *
Access-Control-Allow-Methods = GET, POST, PUT, DELETE, OPTIONS, PROPFIND, PROPPATCH, REPORT, MKCALENDAR, MKCOL
Access-Control-Allow-Headers = Authorization, Content-Type, Depth, If-Match, If-None-Match, Lock-Token, Overwrite, Prefer, Destination, X-Client
Access-Control-Expose-Headers = ETag, DAV
Access-Control-Allow-Credentials = true
CONF

# ── Kalender Ordner ──
COLROOT="/data/collections/collection-root"
USERDIR="${COLROOT}/${CALDAV_USER}"
CALDIR="${USERDIR}/calendar"

mkdir -p "${CALDIR}"

# Radicale braucht exakt dieses Format für die .props Dateien
if [ ! -f "${COLROOT}/.Radicale.props" ]; then
  printf '{}' > "${COLROOT}/.Radicale.props"
fi

if [ ! -f "${USERDIR}/.Radicale.props" ]; then
  printf '{"D:displayname": "%s", "tag": "VCADDRESSBOOK"}' "${CALDAV_USER}" > "${USERDIR}/.Radicale.props"
fi

if [ ! -f "${CALDIR}/.Radicale.props" ]; then
  printf '{"C:supported-calendar-component-set": "VEVENT", "D:displayname": "Chez Philipp", "tag": "VCALENDAR", "color": "#c9957a"}' > "${CALDIR}/.Radicale.props"
fi

# Berechtigungen
chmod -R 755 /data/collections
chmod 600 /data/users

echo ">>> Setup abgeschlossen!"
echo ">>> CalDAV URL: http://SERVER-IP:5232/${CALDAV_USER}/calendar/"
