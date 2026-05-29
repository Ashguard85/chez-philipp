#!/bin/sh
set -e

echo ">>> Injecting CalDAV config..."

sed -i "s|const CALDAV_URL = .*|const CALDAV_URL = 'http://${CALDAV_HOST}:${CALDAV_PORT}/${CALDAV_USER}/calendar/';|" /usr/share/nginx/html/index.html
sed -i "s|const CALDAV_USER = .*|const CALDAV_USER = '${CALDAV_USER}';|" /usr/share/nginx/html/index.html
sed -i "s|const CALDAV_PASS = .*|const CALDAV_PASS = '${CALDAV_PASS}';|" /usr/share/nginx/html/index.html

echo ">>> Starting nginx..."
exec nginx -g 'daemon off;'
