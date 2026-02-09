# 存档系统测试指南

## ✅ 已实现的功能

### 1. 数据库持久化
- 新增 `game_saves` 表，存储完整的游戏状态
- 支持多存档位（当前默认存档位1）
- 记录游戏版本、学期信息、保存时间

### 2. 保存机制
**手动保存：**
- 顶部导航栏"保存"按钮 → 保存到数据库，继续游戏
- 快捷键：点击"保存"按钮

**退出保存：**
- 顶部导航栏"退出"按钮 → 弹出确认弹窗
- 选项1：保存并退出 → 保存到数据库 + 清理Redis + 返回首页
- 选项2：不保存退出 → 直接清理Redis + 返回首页
- 选项3：取消 → 继续游戏

**自动保存：**
- 每学期结束时自动保存到数据库
- 毕业时自动保存

### 3. 加载机制
- 登录游戏时自动检测数据库存档
- 优先使用Redis缓存（性能优化）
- Redis缺失时从数据库加载
- 兼容旧版本存档（自动修复缺失字段）

### 4. 数据清理
- 退出游戏后自动清理Redis缓存
- 防止内存泄漏和数据混乱

---

## 🧪 测试步骤

### 测试1：手动保存功能
1. 登录游戏，游玩一段时间
2. 点击顶部"保存"按钮
3. 查看控制台是否显示：`[SaveManager] Manual save requested`
4. 应该看到提示："游戏已保存"（3秒后消失）
5. 检查数据库：
   ```bash
   docker-compose exec db psql -U zju -d zjuers -c "SELECT user_id, semester_index, saved_at FROM game_saves;"
   ```

### 测试2：保存并退出
1. 登录游戏，游玩一段时间
2. 点击顶部"退出"按钮
3. 应弹出确认弹窗，包含三个按钮：
   - "取消" → 关闭弹窗，继续游戏
   - "不保存退出" → 确认提示 → 直接返回首页
   - "保存并退出" → 显示"正在保存游戏..." → 1.5秒后返回首页
4. 检查数据库是否有存档
5. 检查Redis是否已清理：
   ```bash
   docker-compose exec redis redis-cli KEYS "player:*"
   ```
   应该返回空（如果没有其他在线玩家）

### 测试3：加载存档
1. 确保上一步已保存存档
2. 重新登录游戏
3. 查看控制台是否显示：
   - `No Redis data found for XXX, checking database...`
   - `Successfully loaded save from database for XXX`
4. 验证游戏状态是否正确恢复：
   - 用户名、学期显示正确
   - 课程进度显示正确
   - 倒计时从上次保存时间继续

### 测试4：自动保存（学期结束）
1. 登录游戏，完成一学期（参加期末考试）
2. 查看后端日志：
   ```bash
   docker-compose logs backend --tail=50
   ```
3. 应该看到：`Auto-save triggered at end of semester for user X`
4. 检查数据库的 `saved_at` 时间是否更新

### 测试5：多用户隔离
1. 创建两个用户账号
2. 用户A保存并退出
3. 用户B登录游戏
4. 验证用户B看到的是自己的存档，而非用户A的
5. 用户A重新登录，验证数据未被污染

### 测试6：页面刷新（不应丢失数据）
1. 登录游戏，游玩一段时间
2. 按 F5 刷新页面
3. 验证游戏状态是否保留（Redis缓存仍存在）
4. 再次刷新，验证一致性

### 测试7：浏览器关闭保护
1. 登录游戏
2. 尝试关闭浏览器标签页
3. 应看到浏览器提示："游戏正在进行中，建议先保存进度再离开。"
4. 选择"离开" → 数据保留在Redis中（24小时内仍可恢复）
5. 选择"留在页面" → 继续游戏

---

## 🔍 故障排查

### 问题1：保存失败
**症状：** 点击"保存"按钮后显示"保存失败，请重试"

**排查步骤：**
1. 检查后端日志：
   ```bash
   docker-compose logs backend | grep -i "save"
   ```
2. 检查数据库连接：
   ```bash
   docker-compose ps
   ```
3. 检查表是否存在：
   ```bash
   docker-compose exec db psql -U zju -d zjuers -c "\dt"
   ```

### 问题2：加载存档失败
**症状：** 重新登录后数据丢失，重新开始游戏

**排查步骤：**
1. 检查数据库是否有存档：
   ```bash
   docker-compose exec db psql -U zju -d zjuers -c "SELECT * FROM game_saves WHERE user_id = X;"
   ```
2. 检查后端日志是否有加载错误
3. 验证Redis是否已清理（可能Redis中有旧数据干扰）

### 问题3：前端弹窗不显示
**症状：** 点击"退出"按钮没有反应

**排查步骤：**
1. 打开浏览器控制台（F12）
2. 查看是否有JavaScript错误
3. 检查 `saveManager` 是否正确初始化：在控制台输入 `saveManager`
4. 强制刷新页面（Ctrl + F5）清除缓存

### 问题4：旧用户数据不兼容
**症状：** 旧用户登录后显示undefined

**解决方案：** 已自动修复，代码会补充缺失的字段
```python
# 在 game.py 情况C中自动修复
repair_fields = {}
if not stats.get("username"):
    repair_fields["username"] = username
# ... 等等
```

---

## 📊 数据库查询示例

### 查看所有存档
```sql
SELECT 
    user_id, 
    save_slot,
    semester_index,
    game_version,
    created_at,
    saved_at
FROM game_saves
ORDER BY saved_at DESC;
```

### 查看特定用户的存档详情
```sql
SELECT 
    stats_data->>'username' AS username,
    stats_data->>'semester' AS semester,
    stats_data->>'energy' AS energy,
    stats_data->>'sanity' AS sanity,
    saved_at
FROM game_saves
WHERE user_id = 1;
```

### 删除特定存档
```sql
DELETE FROM game_saves WHERE user_id = 1 AND save_slot = 1;
```

---

## 🎯 下一步优化建议

1. **多存档支持**：允许用户创建3个存档位
2. **存档预览**：加载前显示存档信息（学期、GPA、保存时间）
3. **自动保存间隔**：每10分钟自动保存一次
4. **存档云同步**：跨设备同步存档
5. **存档导出**：支持导出JSON文件
6. **存档回滚**：保留最近5个自动保存，支持回滚

---

## 🛡️ 安全注意事项

1. **数据验证**：保存前验证数据完整性
2. **防重复保存**：debounce机制，防止频繁点击
3. **错误恢复**：保存失败时保留Redis数据
4. **并发控制**：同用户同时只能有一个活跃连接
5. **数据加密**：敏感数据可考虑加密存储（可选）
