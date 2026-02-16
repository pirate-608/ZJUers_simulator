# ==========================================
# Stage 1: C 语言编译环境 (Builder)
# ==========================================
FROM python:3.11-slim-bookworm AS builder

# 1. 更换国内源 (可选，加快构建速度，视网络情况而定)
# RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list
# 或
# RUN sed -i 's/pypi.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list

RUN pip install --upgrade pip

# 2. 安装编译依赖 (gcc, cmake, make)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cmake \
    make \
    && rm -rf /var/lib/apt/lists/*

# 3. 设置工作目录
WORKDIR /build_c

# 4. 复制 C 源码和 CMake 配置
COPY c_modules/ ./c_modules/

# 5. 执行编译
# 假设 CMakeLists.txt 在 c_modules/ 下
WORKDIR /build_c/c_modules
RUN mkdir build && cd build && cmake .. && make
# 编译完成后，libjudge.so 应该位于 /build_c/c_modules/build/libjudge.so


# ==========================================
# Stage 2: Python 运行环境 (Runtime)
# ==========================================
FROM python:3.11-slim-bookworm

WORKDIR /app

# 1. 安装系统运行时依赖 (PostgreSQL 驱动通常需要 libpq5)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. 创建存放动态库的目录
RUN mkdir -p /app/lib

# 3. [关键步骤] 从 Stage 1 复制编译好的动态库
COPY --from=builder /build_c/c_modules/build/libjudge.so /app/lib/libjudge.so

# 4. 设置环境变量，确保 Python 能加载到动态库
# 这样在 Python 中加载时，ctypes 可以自动搜索到这个目录
ENV LD_LIBRARY_PATH=/app/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

# 5. 复制 Python 依赖配置
COPY requirements.txt .

# 6. 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 7. 复制项目所有源码
# 包含 app, static, templates, world 等目录
COPY . .

# 8. 暴露端口
EXPOSE 8000

# 9. 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]