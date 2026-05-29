#!/bin/sh
set -e

echo ">>> Chez Philipp Setup starting..."

apk add --no-cache python3 py3-pip > /dev/null 2>&1
pip install bcrypt --quiet --break-system-packages > /dev/null 2>&1

# Create user if not exists
if [ ! -f /data/users ]; then
  echo ">>> Creating CalDAV user: ${CALDAV_USER}"
  python3 -c "
import bcrypt, os
user = os.environ['CALDAV_USER']
pw   = os.environ['CALDAV_PASS']
h    = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
open('/data/users','w').write(f'{user}:{h}\n')
print('User created:', user)
"
else
  echo ">>> User already exists, skipping."
fi

# Create calendar folder structure
COLPATH="/data/collections/collection-root/${CALDAV_USER}"
mkdir -p "${COLPATH}/calendar"

if [ ! -f "${COLPATH}/.Radicale.props" ]; then
  echo ">>> Creating calendar collection..."
  printf '{"D:displayname": "%s"}' "${CALDAV_USER}" > "${COLPATH}/.Radicale.props"
  printf '{"D:displayname": "Chez Philipp", "tag": "VCALENDAR"}' > "${COLPATH}/calendar/.Radicale.props"
else
  echo ">>> Calendar already exists, skipping."
fi

# Write radicale config
echo ">>> Writing radicale config..."
cat > /config/radicale.conf << EOF
[server]
hosts = 0.0.0.0:5232

[auth]
type = htpasswd
htpasswd_filename = /data/users
htpasswd_encryption = bcrypt

[storage]
filesystem_folder = /data/collections

[logging]
level = info

[headers]
Access-Control-Allow-Origin = *
Access-Control-Allow-Methods = GET, POST, PUT, DELETE, OPTIONS, PROPFIND, PROPPATCH, REPORT, MKCALENDAR, MKCOL
Access-Control-Allow-Headers = Authorization, Content-Type, Depth, If-Match, If-None-Match, Lock-Token, Overwrite, Prefer, Destination, X-Client
Access-Control-Expose-Headers = ETag, DAV
Access-Control-Allow-Credentials = true
EOF

echo ">>> Setup complete!"
