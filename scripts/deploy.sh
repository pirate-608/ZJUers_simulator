#!/bin/bash
# ZJUers Simulator - Linux/macOS 一键部署脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "================================================================"
echo "  🎓 ZJUers Simulator - Docker 一键部署"
echo "  📦 基于Docker的完整部署方案"  
echo "================================================================"
echo ""

# 检查Python
echo -e "${BLUE}[1/3] 检查Python环境...${NC}"
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✅ Python已安装${NC}"
    python3 --version
    echo ""
    echo -e "${BLUE}[2/3] 运行自动部署脚本...${NC}"
    cd "$(dirname "$0")/.."
    python3 scripts/deploy.py
    exit 0
elif command -v python &> /dev/null; then
    echo -e "${GREEN}✅ Python已安装${NC}"
    python --version
    echo ""
    echo -e "${BLUE}[2/3] 运行自动部署脚本...${NC}"
    cd "$(dirname "$0")/.."
    python scripts/deploy.py  
    exit 0
else
    echo -e "${YELLOW}⚠️  未找到Python，使用备用方案...${NC}"
fi

# 备用方案：直接使用docker-compose
echo -e "${BLUE}[备用] 检查Docker环境...${NC}"
cd "$(dirname "$0")/.."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker未安装，请先安装Docker${NC}"
    echo ""
    echo "安装方法："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macOS: 下载 Docker Desktop - https://www.docker.com/products/docker-desktop/"
    else
        echo "Linux: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
    fi
    exit 1
fi

echo -e "${GREEN}✅ Docker已安装${NC}"
docker --version

# 检查Docker Compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose未安装${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker Compose已安装${NC}"

echo ""
echo -e "${BLUE}[2/3] 配置环境变量...${NC}"
if [ ! -f ".env" ]; then
    echo ""
    echo "================================================================"
    echo -e "  ${BLUE}🤖 AI功能配置 (可选)${NC}"
    echo "================================================================"
    echo "AI功能需要阿里云百炼平台的API密钥"
    echo "详细获取步骤请查看 scripts/README.md"
    echo ""
    
    read -p "是否现在配置AI功能? (y/n) [默认:n]: " configure_ai
    configure_ai=${configure_ai:-n}
    
    if [[ "$configure_ai" =~ ^[Yy]$ ]]; then
        echo ""
        echo "📋 获取步骤："
        echo "1. 访问阿里云百炼: https://bailian.console.aliyun.com"
        echo "2. 登录/注册并完成实名认证"
        echo "3. 开通服务后，进入'密钥管理'创建API Key"
        echo "4. 在'模型服务'中选择模型 (如 qwen-max, qwen-plus, qwen-turbo)"
        echo ""
        
        read -p "请输入API Key (以sk-开头): " llm_api_key
        
        echo ""
        echo "💡 推荐模型："
        echo "  - qwen-max (最强能力，适合复杂任务)"
        echo "  - qwen-plus (平衡性能与成本)"
        echo "  - qwen-turbo (快速响应，低成本)"
        
        read -p "请输入模型名称 [默认: qwen-turbo]: " llm_model
        llm_model=${llm_model:-qwen-turbo}
    else
        llm_api_key=""
        llm_model="qwen-turbo"
    fi
    
    echo ""
    echo -e "${RED}🔒 安全警告：${NC}"
    echo -e "${YELLOW}  由于未检测到Python环境，此部署使用简单默认密钥${NC}"
    echo -e "  数据库密码: zjuers123456"
    echo -e "  安全密钥: zjuers-default-2026"
    echo -e "${RED}  🔴 警告: 此配置存在安全风险，仅适用于本地测试${NC}"
    echo -e "  如需生产环境部署，请安装Python并使用自动部署脚本"
    echo ""
    read -p "按回车继续..."
    
    cat > .env << EOF
# ZJUers Simulator Docker 部署配置
# 警告: 使用默认密钥，存在安全风险
# 生成于 $(date)

DATABASE_URL=postgresql+asyncpg://zju:zjuers123456@db/zjuers
POSTGRES_PASSWORD=zjuers123456
SECRET_KEY=zjuers-default-2026
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=$llm_api_key
LLM=$llm_model
REDIS_URL=redis://redis:6379/0
EOF
    
    echo -e "${GREEN}✅ 环境文件已创建${NC}"
    if [ -n "$llm_api_key" ]; then
        echo -e "${GREEN}✅ AI功能已配置 (模型: $llm_model)${NC}"
    else
        echo -e "${YELLOW}ℹ️ AI功能未配置，如需使用请编辑 .env 文件${NC}"
    fi
else
    echo -e "${GREEN}✅ 环境文件已存在${NC}"
fi

echo ""
echo -e "${BLUE}[3/3] 启动Docker服务...${NC}" 
$COMPOSE_CMD up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "================================================================"
    echo -e "  ${GREEN}🎉 部署完成！${NC}"
    echo "================================================================"  
    echo "  🌐 访问地址: http://localhost:8000"
    echo "  📊 管理面板: $COMPOSE_CMD ps"
    echo "  📋 查看日志: $COMPOSE_CMD logs -f"
    echo "  ⏹  停止服务: $COMPOSE_CMD down"
    echo "================================================================"
    echo ""
    
    echo -e "${YELLOW}⏳ 等待服务启动完成...${NC}"
    sleep 5
    
    echo -e "${BLUE}🌐 正在打开浏览器...${NC}"
    if command -v xdg-open > /dev/null; then
        xdg-open http://localhost:8000 &
    elif command -v open > /dev/null; then
        open http://localhost:8000 &
    else
        echo "请手动访问: http://localhost:8000"
    fi
    
    echo ""
    echo -e "${YELLOW}💡 提示: 服务已在后台运行${NC}"
    echo "   如需停止服务请运行: $COMPOSE_CMD down"
else
    echo -e "${RED}❌ 启动失败，请检查Docker是否正在运行${NC}"
    exit 1
fi