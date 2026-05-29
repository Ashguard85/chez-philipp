#!/bin/sh
set -e
echo ">>> Injecting config into index.html..."

CALDAV_FULL="http://${CALDAV_HOST}:${CALDAV_PORT}/${CALDAV_USER}/calendar/"

sed -i "s|%%CALDAV_URL%%|${CALDAV_FULL}|g"  /usr/share/nginx/html/index.html
sed -i "s|%%CALDAV_USER%%|${CALDAV_USER}|g" /usr/share/nginx/html/index.html
sed -i "s|%%CALDAV_PASS%%|${CALDAV_PASS}|g" /usr/share/nginx/html/index.html
sed -i "s|%%ADMIN_PIN%%|${ADMIN_PIN}|g"     /usr/share/nginx/html/index.html

echo ">>> Config injected. Starting nginx..."
exec nginx -g 'daemon off;'
