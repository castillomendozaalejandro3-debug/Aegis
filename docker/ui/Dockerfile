FROM node:20-slim AS builder

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build production bundle
RUN npm run build

# Production stage with nginx
FROM nginx:alpine

# Security: non-root user for nginx
RUN addgroup -g 1001 -S aegis && \
    adduser -u 1001 -S aegis -G aegis

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Security headers
RUN echo 'server_tokens off;' > /etc/nginx/conf.d/security.conf && \
    echo 'add_header X-Frame-Options "DENY" always;' >> /etc/nginx/conf.d/security.conf && \
    echo 'add_header X-Content-Type-Options "nosniff" always;' >> /etc/nginx/conf.d/security.conf && \
    echo 'add_header X-XSS-Protection "1; mode=block" always;' >> /etc/nginx/conf.d/security.conf && \
    echo 'add_header Referrer-Policy "strict-origin-when-cross-origin" always;' >> /etc/nginx/conf.d/security.conf

# Set permissions
RUN chown -R aegis:aegis /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]
