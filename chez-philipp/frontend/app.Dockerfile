FROM nginx:alpine

ARG CALDAV_USER=philipp
ARG CALDAV_PASS=geheim123
ARG ADMIN_PIN=1234

COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/sw.js /usr/share/nginx/html/sw.js
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Config mit Build-Timestamp als Cache-Buster
RUN BUILD_TS=$(date +%s) && \
    printf "const API = window.location.protocol + '//' + window.location.hostname + ':3200/api';\n\
const CALDAV_URL = window.location.protocol + '//' + window.location.hostname + ':3200/caldav/%s/calendar/';\n\
const CALDAV_USER = '%s';\n\
const CALDAV_PASS = '%s';\n\
const ADMIN_PIN_ENV = '%s';\n\
const BUILD_VERSION = '%s';\n" \
    "$CALDAV_USER" "$CALDAV_USER" "$CALDAV_PASS" "$ADMIN_PIN" "$BUILD_TS" \
    > /usr/share/nginx/html/config.js && \
    # Inject version into service worker
    sed -i "s/BUILD_VERSION/$BUILD_TS/g" /usr/share/nginx/html/sw.js

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
