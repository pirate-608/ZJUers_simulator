@echo off
REM ZJUers Simulator - Windows 一键部署脚本
chcp 65001 >nul
title ZJUers Simulator - Docker 一键部署

echo.
echo ================================================================
echo   🎓 ZJUers Simulator - Docker 一键部署
echo   📦 基于Docker的完整部署方案
echo ================================================================
echo.

REM 检查Python
echo [1/3] 检查Python环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到Python，正在使用备用方案...
    
    REM 备用方案：直接使用docker-compose
    echo [备用] 检查Docker环境...
    docker --version >nul 2>&1
    if errorlevel 1 (
        echo ❌ Docker未安装，请先安装Docker Desktop
        echo 📥 下载地址: https://www.docker.com/products/docker-desktop/
        pause
        exit /b 1
    )
    
    echo ✅ Docker已安装
    goto DOCKER_DEPLOY
) else (
    echo ✅ Python已安装
    python --version
    echo.
    echo [2/3] 运行自动部署脚本...
    python deploy.py
    goto END
)

:DOCKER_DEPLOY
echo.
echo [2/3] 创建默认环境配置...
if not exist ".env" (
    echo # ZJUers Simulator Docker 部署配置 > .env
    echo DATABASE_URL=postgresql+asyncpg://zju:zjuers123456@db/zjuers >> .env
    echo POSTGRES_PASSWORD=zjuers123456 >> .env
    echo SECRET_KEY=zjuers-simulator-docker-secret-key-2026 >> .env
    echo LLM_API_KEY= >> .env
    echo LLM_BASE_URL=https://api.openai.com/v1 >> .env
    echo LLM=gpt-3.5-turbo >> .env
    echo ✅ 环境文件已创建
) else (
    echo ✅ 环境文件已存在
)

echo.
echo [3/3] 启动Docker服务...
docker compose up -d --build

if errorlevel 1 (
    echo ❌ 启动失败，请检查Docker是否正在运行
    pause
    exit /b 1
)

echo.
echo ================================================================
echo   🎉 部署完成！
echo ================================================================
echo   🌐 访问地址: http://localhost:8000
echo   📊 管理面板: docker compose ps
echo   📋 查看日志: docker compose logs -f  
echo   ⏹  停止服务: docker compose down
echo ================================================================
echo.

echo ⏳ 等待服务启动完成...
timeout /t 5 /nobreak >nul

echo 🌐 正在打开浏览器...
start http://localhost:8000

:END
echo.
echo 💡 提示: 按任意键关闭此窗口（不会停止服务）
echo    如需停止服务请运行: docker compose down
pause >nul