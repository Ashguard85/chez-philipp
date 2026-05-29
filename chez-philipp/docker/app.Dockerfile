FROM nginx:alpine

COPY frontend/index.html /usr/share/nginx/html/index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/app-entrypoint.sh /app-entrypoint.sh
RUN chmod +x /app-entrypoint.sh

CMD ["/app-entrypoint.sh"]
