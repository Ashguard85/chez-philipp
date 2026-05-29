#!/bin/sh
set -e
echo ">>> Writing config.js..."

cat > /usr/share/nginx/html/config.js << CONFIGEOF
const API = window.location.protocol + '//' + window.location.hostname + ':3201';
const ADMIN_PIN_ENV = '${ADMIN_PIN}';
const CALDAV_URL  = 'http://${CALDAV_HOST}:${CALDAV_PORT}/${CALDAV_USER}/calendar/';
const CALDAV_USER = '${CALDAV_USER}';
const CALDAV_PASS = '${CALDAV_PASS}';
CONFIGEOF

echo ">>> config.js written. Starting nginx..."
exec nginx -g 'daemon off;'
