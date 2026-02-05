@echo off
REM ZJUers Simulator - 停止服务脚本
chcp 65001 >nul
title ZJUers Simulator - 停止服务

echo.
echo ============================================
echo   ⏹ ZJUers Simulator - 停止服务
echo ============================================
echo.

echo 正在停止Docker服务...
docker compose down

if errorlevel 1 (
    echo ❌ 停止失败，可能服务未在运行
) else (
    echo ✅ 服务已停止
)

echo.
echo ============================================
echo   💡 提示
echo ============================================
echo   🔄 重新启动: 运行 deploy.bat
echo   📊 查看状态: docker compose ps
echo   🗑️  清理数据: docker compose down -v
echo ============================================
echo.

pause