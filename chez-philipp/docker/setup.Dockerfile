FROM alpine:latest

RUN apk add --no-cache python3 py3-pip && \
    pip install bcrypt --quiet --break-system-packages

COPY scripts/setup-cal.sh /setup-cal.sh
RUN chmod +x /setup-cal.sh

CMD ["/setup-cal.sh"]
