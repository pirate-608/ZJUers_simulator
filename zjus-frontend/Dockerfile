# ==================================
# Stage 1: Build the Vue application
# ==================================
FROM node:18-alpine AS builder

WORKDIR /app

# 先复制 package.json 利用缓存
COPY package.json package-lock.json* ./
RUN npm install

# 复制全部前端源码并打包 (这一步会自动生成 /app/dist 目录)
COPY . .
RUN npm run build

# ==================================
# Stage 2: Serve with Nginx
# ==================================
FROM nginx:alpine

# 将 Stage 1 构建产生好的 dist 目录提取并放置到 nginx 默认或指定目录下
# (在原有 docker-compose 里面路径为 /usr/share/nginx/game-frontend)
COPY --from=builder /app/dist /usr/share/nginx/game-frontend

# 由于 docker-compose 仍然挂载了原本根目录下的 nginx 配置文件
# 这里为了让容器也能脱离 docker-compose 独立运行测试，我们会放一个默认入口也可以，
# 但基于原方案，我们在 docker-compose 里通过挂载配置文件来复用即可。

EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]
