FROM python:3.11-alpine

RUN pip install radicale bcrypt passlib

RUN mkdir -p /data/collections

COPY config /etc/radicale/config
COPY setup.sh /setup.sh
RUN chmod +x /setup.sh

EXPOSE 5232

CMD ["/setup.sh"]
