FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS frontend-runtime

# Install ngrok (download binary) and make it executable
RUN apk add --no-cache curl && \
    curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-linux-amd64.tgz | tar -xz -C /usr/local/bin && \
    chmod +x /usr/local/bin/ngrok

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Make ngrok token configurable at runtime
ENV NGROK_AUTHTOKEN=

# Add entrypoint that starts nginx and ngrok
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
