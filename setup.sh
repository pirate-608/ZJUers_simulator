#!/bin/bash
# Linux / macOS Setup Script - ZJUers Simulator

echo -e "\033[36m========================================\033[0m"
echo -e "\033[36m  ZJUers Simulator - 本地启动向导\033[0m"
echo -e "\033[36m========================================\033[0m"

# 1. Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "\033[31m错误: 未检测到 Docker。请先安装并启动 Docker 引擎。\033[0m"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "\033[31m错误: Docker 未启动（或者是由于权限不足未授权运行）。请开启 Docker Daemon 环境。\033[0m"
    exit 1
fi

# 2. Copy docker-compose override template (required for local build)
if [ ! -f "docker-compose.override.yml" ]; then
    cp docker-compose.override.example docker-compose.override.yml
    echo -e "\033[32m已创建 docker-compose.override.yml（本地构建配置）\033[0m"
fi

# 3. Check if .env exists
if [ -f ".env" ]; then
    read -p "检测到已存在配置文件 (.env)。是否直接使用已有配置启动？(Y/n, 默认 Y): " useExisting
    useExisting=${useExisting:-Y}
    if [[ "$useExisting" == "Y" || "$useExisting" == "y" ]]; then
        echo -e "\033[32m使用已有配置启动...\033[0m"
        docker compose up -d --build
        if [ $? -eq 0 ]; then
            echo -e "\033[32m启动成功！请在浏览器中访问 http://localhost\033[0m"
            if command -v open &> /dev/null; then open "http://localhost";
            elif command -v xdg-open &> /dev/null; then xdg-open "http://localhost"; fi
        else
            echo -e "\033[31m启动失败，请检查上方日志输出信息。\033[0m"
        fi
        exit 0
    fi
fi

# 4. Invite Code Configuration
echo -e "\n\033[33m=== 邀请码配置 ===\033[0m"
echo "游戏使用邀请码进行入学认证，请设置至少一个邀请码。"
read -p "请输入邀请码（多个用逗号分隔，如 CODE1,CODE2）: " inviteCodes

# 5. LLM Configuration Prompt
echo -e "\n\033[33m=== 大模型配置 ===\033[0m"
echo "游戏核心依赖大模型服务，请选择您在平台已申请密钥的服务商："
echo "1. OpenAI (支持自建代理中转源)"
echo "2. DeepSeek (推荐)"
echo "3. 阿里云通义千问 (Qwen)"
echo "4. 智谱清言 (GLM)"
echo "5. 月之暗面 (Moonshot/Kimi)"
echo "6. MiniMax"
echo "7. 其他 (自定义)"
echo "8. 跳过（离线模式，仅使用预编译事件库）"

read -p "请输入对应数字 (默认 1): " providerChoice
providerChoice=${providerChoice:-1}

if [ "$providerChoice" = "8" ]; then
    baseUrl=""
    apiKey=""
    modelName=""
else
    case $providerChoice in
        2) baseUrl="https://api.deepseek.com" ;;
        3) baseUrl="https://dashscope.aliyuncs.com/compatible-mode/v1" ;;
        4) baseUrl="https://open.bigmodel.cn/api/paas/v4" ;;
        5) baseUrl="https://api.moonshot.cn/v1" ;;
        6) baseUrl="https://api.minimax.chat/v1" ;;
        7) read -p "请输入自定义大模型 API 基础URL (例如 https://api.aigc.com/v1): " baseUrl ;;
        *) baseUrl="https://api.openai.com/v1" ;;
    esac
    read -p "请输入您的大模型 API Key: " apiKey
    read -p "请输入使用的模型代号 (如 gpt-4o-mini, deepseek-chat 等): " modelName
fi

# Generate Random keys
secretKey=$(LANG=C tr -dc A-Za-z0-9 </dev/urandom | head -c 32)
adminPwd=$(LANG=C tr -dc A-Za-z0-9 </dev/urandom | head -c 16)
sessionSecret=$(LANG=C tr -dc A-Za-z0-9 </dev/urandom | head -c 32)
dbPwd=$(LANG=C tr -dc A-Za-z0-9 </dev/urandom | head -c 24)

echo -e "\n\033[33m正在后台为您生成安全配置及密钥环境...\033[0m"

cat > .env <<EOF
# 自动生成的环境配置 - 本地启动向导
ENVIRONMENT=development

# 邀请码
INVITE_CODES=$inviteCodes

# 数据库
DATABASE_URL=postgresql+asyncpg://zju:$dbPwd@db:5432/zjus
POSTGRES_PASSWORD=$dbPwd

# LLM 配置
LLM_API_KEY=$apiKey
LLM_BASE_URL=$baseUrl
LLM=$modelName

# MiniMax M2-her 配置（钉钉消息 RP 生成，可选）
MINIMAX_API_KEY=
MINIMAX_MODEL=minimax-m2-her
MINIMAX_BASE_URL=https://api.minimax.chat/v1/text/chatcompletion_v2

# 安全配置 (随机生成)
SECRET_KEY=$secretKey
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$adminPwd
ADMIN_SESSION_SECRET=$sessionSecret
EOF

echo -e "\033[32m环境配置已成功落盘！开始拉起底层服务 (首次可能需下载镜像)...\033[0m"
docker compose up -d --build

if [ $? -eq 0 ]; then
    echo -e "\033[32m\n容器部署成功！尝试为您弹起网页界面 (或手动访问 http://localhost)\033[0m"
    sleep 3
    if command -v open &> /dev/null; then open "http://localhost";
    elif command -v xdg-open &> /dev/null; then xdg-open "http://localhost"; fi
else
    echo -e "\033[31m启动过程中抛出异常，请排查上方的红色日志！\033[0m"
fi
