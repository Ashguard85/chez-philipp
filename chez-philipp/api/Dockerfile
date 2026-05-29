FROM node:20-alpine
WORKDIR /app
COPY server.js .
RUN mkdir -p /data
EXPOSE 3201
CMD ["node", "server.js"]
