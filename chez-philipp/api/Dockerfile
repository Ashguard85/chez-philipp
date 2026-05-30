FROM node:20-alpine
RUN apk add --no-cache python3 make g++
WORKDIR /app
COPY api/server.js .
RUN npm init -y && npm install better-sqlite3 --build-from-source
RUN mkdir -p /data
EXPOSE 3201
CMD ["node", "server.js"]
