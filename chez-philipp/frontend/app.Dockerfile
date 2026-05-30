FROM nginx:alpine

# Build-time config — set via docker-compose build args
ARG CALDAV_USER=philipp
ARG CALDAV_PASS=geheim123
ARG ADMIN_PIN=1234

# Copy app files
COPY frontend/index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Bake config.js directly into image at build time — no runtime tricks needed
RUN printf "const API = window.location.protocol + '//' + window.location.hostname + ':3201';\n\
const CALDAV_URL = window.location.protocol + '//' + window.location.hostname + ':5232/%s/calendar/';\n\
const CALDAV_USER = '%s';\n\
const CALDAV_PASS = '%s';\n\
const ADMIN_PIN_ENV = '%s';\n" \
  "$CALDAV_USER" "$CALDAV_USER" "$CALDAV_PASS" "$ADMIN_PIN" \
  > /usr/share/nginx/html/config.js

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
