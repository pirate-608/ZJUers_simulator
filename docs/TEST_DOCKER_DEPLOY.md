# 🧪 立即测试 Docker 一键部署

## 快速测试新功能

您现在可以立即测试Docker一键部署功能：

### ✅ Windows 用户
```powershell
# 1. 双击运行 scripts\deploy.bat
scripts\deploy.bat

# 或在PowerShell中运行：
.\scripts\deploy.bat
```

### ✅ Linux/macOS 用户  
```bash
# 1. 给脚本添加执行权限
chmod +x scripts/deploy.sh scripts/stop.sh

# 2. 运行部署脚本
./scripts/deploy.sh
```

### ✅ 跨平台（Python方式）
```bash
# 使用Python脚本（推荐，功能最全）
python scripts/deploy.py
```

---

## 🔍 测试流程

### 1. 环境检查
脚本会自动检查：
- ✅ Docker是否安装
- ✅ Docker Compose是否可用
- ✅ 端口8000是否空闲

### 2. 自动配置
- ✅ 创建 `.env` 环境文件
- ✅ 设置默认密码和密钥
- ✅ 配置数据库连接

### 3. 镜像构建
- ✅ 自动构建Docker镜像（首次需要几分钟）
- ✅ 或拉取预构建镜像（如果可用）
- ✅ 显示构建进度

### 4. 服务启动
- ✅ 启动PostgreSQL数据库
- ✅ 启动Redis缓存
- ✅ 启动Web应用
- ✅ 等待服务就绪

### 5. 自动打开
- ✅ 浏览器自动打开 http://localhost:8000
- ✅ 显示管理命令提示

---

## 📊 预期输出

成功运行后您将看到：

```
================================================================
  🎉 部署完成！
================================================================
  🌐 访问地址: http://localhost:8000
  📊 管理面板: docker compose ps
  📋 查看日志: docker compose logs -f  
  ⏹  停止服务: docker compose down
================================================================
```

浏览器会自动打开游戏页面！

---

## 🔧 管理命令

### 查看服务状态
```bash
docker compose ps
```

### 查看实时日志
```bash
docker compose logs -f
```

### 停止服务
```bash
# 使用停止脚本
scripts\stop.bat        # Windows
./scripts/stop.sh       # Linux/Mac

# 或直接使用Docker命令
docker compose down
```

### 重启服务
```bash
docker compose restart
```

### 完全清理（包括数据）
```bash
docker compose down -v
```

---

## ⚠️ 故障排除

### Docker未启动
**现象**：提示"Docker daemon is not running"
**解决**：
- Windows: 启动Docker Desktop应用
- Linux: `sudo systemctl start docker`
- macOS: 启动Docker.app

### 端口被占用
**现象**：提示"Port 8000 is already in use"
**解决**：
```bash
# 查看占用端口的进程
netstat -tulpn | grep 8000  # Linux
netstat -ano | findstr :8000  # Windows

# 停止占用进程或修改docker-compose.yml中的端口
```

### 镜像构建失败
**现象**：构建过程中出错
**解决**：
```bash
# 清理Docker缓存后重试
docker system prune -f
docker compose build --no-cache
```

---

## 🎯 下一步

测试成功后，您可以：

1. **开发**: 修改代码，Docker会自动重载
2. **分发**: 将整个项目文件夹分享给其他用户
3. **云端**: 使用相同配置部署到服务器
4. **CI/CD**: 设置自动化构建和发布

---

## 💡 用户反馈

如果测试过程中遇到任何问题，请：

1. 查看控制台的错误信息
2. 运行 `docker compose logs` 查看详细日志
3. 检查是否有杀毒软件阻止Docker运行
4. 确保有足够的磁盘空间（至少1GB）

**立即开始测试吧！** 🚀