FROM alpine:latest
RUN apk add --no-cache python3 py3-pip && pip install bcrypt --quiet --break-system-packages
COPY scripts/setup.sh /setup.sh
RUN chmod +x /setup.sh
CMD ["/setup.sh"]
