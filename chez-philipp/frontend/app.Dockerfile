FROM nginx:alpine

ARG CALDAV_USER=philipp
ARG CALDAV_PASS=geheim123
ARG ADMIN_PIN=1234

COPY frontend/index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Alles über nginx :3200 — kein CORS, iOS via Cloudflare Tunnel
RUN printf "const API = window.location.protocol + '//' + window.location.hostname + ':3200/api';\n\
const CALDAV_URL = window.location.protocol + '//' + window.location.hostname + ':3200/caldav/%s/calendar/';\n\
const CALDAV_USER = '%s';\n\
const CALDAV_PASS = '%s';\n\
const ADMIN_PIN_ENV = '%s';\n" \
  "$CALDAV_USER" "$CALDAV_USER" "$CALDAV_PASS" "$ADMIN_PIN" \
  > /usr/share/nginx/html/config.js

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
