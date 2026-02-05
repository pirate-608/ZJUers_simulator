# 发布版本信息

## 版本号规范

当前版本：**v1.0.0**

### 版本号说明
- **主版本号 (Major)**: 1 - 重大架构变更（从单机版改为Docker版）
- **次版本号 (Minor)**: 0 - 功能性更新
- **修订号 (Patch)**: 0 - Bug修复

### 版本历史

#### v1.0.0 (2026-02-05) - Docker 一键部署版 🐳
- **里程碑**: Docker容器化部署首次发布
- **核心变更**: 
  - 从 PyInstaller 单机打包方案改为 Docker 部署方案
  - 实现跨平台一键部署脚本
  - 集成阿里云百炼 AI 服务
  - 自动化密钥生成和环境配置
  - 移除 nginx 依赖，简化架构

---

## Release 标签建议

### Git 标签命令
```bash
# 创建版本标签
git tag -a v1.0.0 -m "Release v1.0.0 - Docker 一键部署版"

# 推送标签到远程
git push origin v1.0.0

# 或推送所有标签
git push origin --tags
```

### GitHub Release 标题模板

```
ZJUers Simulator v1.0.0 - Docker 一键部署版
```

**备选标题（英文）**：
```
ZJUers Simulator v1.0.0 - Docker One-Click Deployment
```

**备选标题（带Emoji）**：
```
🎓 ZJUers Simulator v1.0.0 - Docker 一键部署版 🐳
```

---

## 发布检查清单

### 发布前准备
- [ ] 确认所有测试通过
- [ ] 更新 `world/game_balance.json` 版本号
- [ ] 更新 `README.md` 版本相关内容
- [ ] 确认 `.env.example` 配置正确
- [ ] 确认部署脚本在各平台测试通过
- [ ] 检查 `.gitignore` 包含敏感文件
- [ ] 准备发布说明文档

### 创建 Release
- [ ] 在 GitHub 创建新 Release
- [ ] 设置正确的 Tag (v1.0.0)
- [ ] 填写 Release Title
- [ ] 复制 Release Body 内容
- [ ] 上传发布包（由 GitHub Actions 自动生成）
- [ ] 标记为最新版本 (Latest Release)

### 发布后
- [ ] 验证下载链接可用
- [ ] 测试从发布包部署流程
- [ ] 更新项目主页链接
- [ ] 发布社区公告（如有）
- [ ] 收集用户反馈

---

## 后续版本规划

### v1.0.x (Patch)
- Bug 修复
- 文档完善
- 小优化改进

### v1.1.0 (Minor)
- 新增游戏功能
- 优化部署流程
- 支持更多配置选项

### v2.0.0 (Major)
- 重大架构升级
- 破坏性变更
- 全新功能模块

---

## 附录：版本号生成工具

### 自动版本号脚本（可选）

```bash
#!/bin/bash
# scripts/bump_version.sh

CURRENT_VERSION="v1.0.0"
echo "当前版本: $CURRENT_VERSION"
echo "选择版本类型:"
echo "1) Patch (v1.0.1)"
echo "2) Minor (v1.1.0)"
echo "3) Major (v2.0.0)"
read -p "请选择 [1-3]: " choice

case $choice in
  1) NEW_VERSION="v1.0.1" ;;
  2) NEW_VERSION="v1.1.0" ;;
  3) NEW_VERSION="v2.0.0" ;;
  *) echo "无效选择"; exit 1 ;;
esac

echo "新版本: $NEW_VERSION"
read -p "确认创建标签? (y/n): " confirm

if [ "$confirm" = "y" ]; then
  git tag -a $NEW_VERSION -m "Release $NEW_VERSION"
  git push origin $NEW_VERSION
  echo "✅ 版本标签已创建并推送"
else
  echo "❌ 取消操作"
fi
```

