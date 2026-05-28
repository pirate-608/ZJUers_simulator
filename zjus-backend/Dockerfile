FROM python:3.11-slim-bookworm

WORKDIR /app

# 1. 安装系统运行时依赖 (PostgreSQL 驱动)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 复制 Python 依赖配置
COPY requirements.txt .

# 3. 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 4. 复制项目所有源码
COPY . .

# 5. 暴露端口
EXPOSE 8000

# 6. 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
