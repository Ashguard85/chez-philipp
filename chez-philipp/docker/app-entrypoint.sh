#!/bin/sh
set -e
echo ">>> Injecting config..."
sed -i "s|CALDAV_URL_PLACEHOLDER|http://${CALDAV_HOST}:${CALDAV_PORT}/${CALDAV_USER}/calendar/|g" /usr/share/nginx/html/index.html
sed -i "s|CALDAV_USER_PLACEHOLDER|${CALDAV_USER}|g"  /usr/share/nginx/html/index.html
sed -i "s|CALDAV_PASS_PLACEHOLDER|${CALDAV_PASS}|g"  /usr/share/nginx/html/index.html
sed -i "s|ADMIN_PIN_VALUE|${ADMIN_PIN}|g"             /usr/share/nginx/html/index.html
echo ">>> Starting nginx..."
exec nginx -g 'daemon off;'
