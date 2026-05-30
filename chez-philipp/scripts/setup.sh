#!/bin/sh
set -e
echo "=== Chez Philipp Setup ==="

apk add --no-cache python3 py3-pip > /dev/null 2>&1
pip install bcrypt --quiet --break-system-packages > /dev/null 2>&1

# Create htpasswd user
if [ ! -f /data/users ]; then
  echo ">>> Creating user: ${CALDAV_USER}"
  python3 -c "
import bcrypt, os
u = os.environ['CALDAV_USER']
p = os.environ['CALDAV_PASS']
h = bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
open('/data/users','w').write(f'{u}:{h}\n')
print('User created:', u)
"
else
  echo ">>> User already exists"
fi

# Radicale config
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

# Create calendar collection
ROOT="/data/collections/collection-root"
UDIR="$ROOT/${CALDAV_USER}"
CDIR="$UDIR/calendar"
mkdir -p "$CDIR"

[ -f "$ROOT/.Radicale.props" ] || printf '{}' > "$ROOT/.Radicale.props"
[ -f "$UDIR/.Radicale.props" ] || printf '{}' > "$UDIR/.Radicale.props"
[ -f "$CDIR/.Radicale.props" ] || printf '{"D:displayname": "Chez Philipp", "tag": "VCALENDAR", "C:supported-calendar-component-set": "VEVENT"}' > "$CDIR/.Radicale.props"

chmod -R 755 /data/collections 2>/dev/null || true
chmod 600 /data/users 2>/dev/null || true

echo "=== Setup complete ==="
