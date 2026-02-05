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
    python3 deploy.py
    exit 0
elif command -v python &> /dev/null; then
    echo -e "${GREEN}✅ Python已安装${NC}"
    python --version
    echo ""
    echo -e "${BLUE}[2/3] 运行自动部署脚本...${NC}"
    python deploy.py  
    exit 0
else
    echo -e "${YELLOW}⚠️  未找到Python，使用备用方案...${NC}"
fi

# 备用方案：直接使用docker-compose
echo -e "${BLUE}[备用] 检查Docker环境...${NC}"
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
echo -e "${BLUE}[2/3] 创建默认环境配置...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << EOF
# ZJUers Simulator Docker 部署配置
DATABASE_URL=postgresql+asyncpg://zju:zjuers123456@db/zjuers
POSTGRES_PASSWORD=zjuers123456
SECRET_KEY=zjuers-simulator-docker-secret-key-2026
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM=gpt-3.5-turbo
EOF
    echo -e "${GREEN}✅ 环境文件已创建${NC}"
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