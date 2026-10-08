#
# ZJUers Simulator frontend image.
#
# Build static assets natively; only the Nginx runtime varies by target platform.
#
FROM --platform=$BUILDPLATFORM node:22-alpine AS builder

WORKDIR /app

# Copy dependency manifests first so Docker can reuse install layers.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:alpine

# Compose mounts the production Nginx config; this default path also supports
# standalone image smoke tests.
COPY --from=builder /app/dist /usr/share/nginx/game-frontend

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
