FROM node:22-alpine AS frontend-build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS frontend-runtime

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf
# Copy built frontend assets
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# Add entrypoint that starts nginx
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]