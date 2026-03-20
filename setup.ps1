# Windows Setup Script - ZJUers Simulator
# Must be run to setup the local simulator purely via Docker

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ZJUers Simulator - 本地启动向导" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Check Docker
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未检测到 Docker。请先安装并启动 Docker Desktop。" -ForegroundColor Red
    Pause
    exit
}

try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) { throw }
}
catch {
    Write-Host "错误: Docker 未启动（或者是由于权限不足）。请先打开 Docker Desktop 并确保其运行正常。" -ForegroundColor Red
    Pause
    exit
}

# 2. Check if .env exists
if (Test-Path ".env") {
    $useExisting = Read-Host "检测到已存在配置文件 (.env)。是否直接使用已有配置启动？(y/n, 默认 y)"
    if ([string]::IsNullOrWhiteSpace($useExisting) -or $useExisting.ToLower() -eq 'y') {
        Write-Host "使用已有配置启动..." -ForegroundColor Green
        docker compose up -d
        if ($?) {
            Write-Host "启动成功！即将为您在浏览器中打开游戏。" -ForegroundColor Green
            Start-Sleep -Seconds 3
            Start-Process "http://localhost"
        } else {
            Write-Host "启动失败，请检查上方日志。" -ForegroundColor Red
        }
        Pause
        exit
    }
}

# 3. LLM Configuration Prompt
Write-Host "`n=== 大模型配置 ===" -ForegroundColor Yellow
Write-Host "游戏核心依赖大模型服务，请选择您在平台已申请密钥的服务商："
Write-Host "1. OpenAI (支持自建代理中转源)"
Write-Host "2. DeepSeek (推荐)"
Write-Host "3. 阿里云通义千问 (Qwen)"
Write-Host "4. 智谱清言 (GLM)"
Write-Host "5. 月之暗面 (Moonshot/Kimi)"
Write-Host "6. MiniMax"
Write-Host "7. 其他 (自定义)"

$providerChoice = Read-Host "请输入对应数字 (默认 1)"
switch ($providerChoice) {
    "2" { $baseUrl = "https://api.deepseek.com" }
    "3" { $baseUrl = "https://dashscope.aliyuncs.com/compatible-mode/v1" }
    "4" { $baseUrl = "https://open.bigmodel.cn/api/paas/v4" }
    "5" { $baseUrl = "https://api.moonshot.cn/v1" }
    "6" { $baseUrl = "https://api.minimax.chat/v1" }
    "7" { $baseUrl = Read-Host "请输入自定义大模型 API 基础URL (例如 https://api.aigc.com/v1)" }
    default { $baseUrl = "https://api.openai.com/v1" }
}

$apiKey = Read-Host "请输入您的大模型 API Key"
$modelName = Read-Host "请输入使用的模型代号 (如 gpt-4o-mini, deepseek-chat 等)"

# Generate Random keys silently
function New-RandomString($length) {
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    $bytes = New-Object byte[] $length
    $rng = [System.Security.Cryptography.RNGCryptoServiceProvider]::Create()
    $rng.GetBytes($bytes)
    $result = ""
    foreach ($b in $bytes) {
        $result += $chars[$b % $chars.Length]
    }
    return $result
}

$secretKey = Generate-RandomString 32
$adminPwd = Generate-RandomString 16
$sessionSecret = Generate-RandomString 32
$dbPwd = Generate-RandomString 24

Write-Host "`n正在后台为您生成安全配置及密钥环境..." -ForegroundColor Yellow

$envContent = @"
# 自动生成的环境配置 - 本地启动向导
ENVIRONMENT=production

# 数据库
DATABASE_URL=postgresql+asyncpg://zju:$dbPwd@db:5432/zjus
POSTGRES_PASSWORD=$dbPwd

# LLM 配置
LLM_API_KEY=$apiKey
LLM_BASE_URL=$baseUrl
LLM=$modelName

# 安全配置 (随机生成)
SECRET_KEY=$secretKey
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$adminPwd
ADMIN_SESSION_SECRET=$sessionSecret
"@

Set-Content -Path ".env" -Value $envContent -Encoding UTF8

Write-Host "环境配置文件已落盘！开始拉起底层服务 (首次可能需要稍长下载时间)..." -ForegroundColor Green
docker compose up -d

if ($?) {
    Write-Host "`n启动成功！即将为您自动弹起网页。" -ForegroundColor Green
    Start-Sleep -Seconds 3
    Start-Process "http://localhost"
} else {
    Write-Host "`n容器部署过程中发生异常，请检查上方日志输出！" -ForegroundColor Red
}

Pause
