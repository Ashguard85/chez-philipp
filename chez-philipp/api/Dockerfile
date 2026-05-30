FROM node:20-alpine
WORKDIR /app
RUN apk add --no-cache python3 make g++
COPY api/server.js .
RUN npm init -y && npm install better-sqlite3
RUN mkdir -p /data
EXPOSE 3201
CMD ["node", "server.js"]
