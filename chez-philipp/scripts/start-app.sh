#!/bin/sh
set -e

echo ">>> Downloading app from GitHub..."
apk add --no-cache curl > /dev/null 2>&1

curl -fsSL "${GITHUB_RAW}/frontend/index.html" \
  | sed "s|const CALDAV_URL = .*|const CALDAV_URL = 'http://${CALDAV_HOST}:${CALDAV_PORT}/${CALDAV_USER}/calendar/';|" \
  | sed "s|const CALDAV_USER = .*|const CALDAV_USER = '${CALDAV_USER}';|" \
  | sed "s|const CALDAV_PASS = .*|const CALDAV_PASS = '${CALDAV_PASS}';|" \
  > /usr/share/nginx/html/index.html

curl -fsSL "${GITHUB_RAW}/nginx.conf" > /etc/nginx/conf.d/default.conf

echo ">>> App ready. Starting nginx..."
exec nginx -g 'daemon off;'
