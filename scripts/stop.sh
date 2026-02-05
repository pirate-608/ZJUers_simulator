#!/bin/bash
# ZJUers Simulator - 停止服务脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "============================================"
echo "  ⏹ ZJUers Simulator - 停止服务"
echo "============================================"
echo ""

echo -e "${BLUE}正在停止Docker服务...${NC}"
cd "$(dirname "$0")/.."

# 检查Docker Compose命令
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo -e "${RED}❌ Docker Compose未找到${NC}"
    exit 1
fi

$COMPOSE_CMD down

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 服务已停止${NC}"
else
    echo -e "${YELLOW}⚠️ 停止失败，可能服务未在运行${NC}"
fi

echo ""
echo "============================================"
echo -e "  ${YELLOW}💡 提示${NC}"
echo "============================================"  
echo "  🔄 重新启动: ./scripts/deploy.sh"
echo "  📊 查看状态: $COMPOSE_CMD ps"
echo "  🗑️  清理数据: $COMPOSE_CMD down -v"
echo "============================================"
echo ""