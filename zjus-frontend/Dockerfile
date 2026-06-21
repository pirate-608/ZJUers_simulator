#
# ZJUers Simulator frontend image.
#
# Stage 1 builds the Vue application; Stage 2 serves static files with Nginx.
#
FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency manifests first so Docker can reuse install layers.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine

# Compose mounts the production Nginx config; this default path also supports
# standalone image smoke tests.
COPY --from=builder /app/dist /usr/share/nginx/game-frontend

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
