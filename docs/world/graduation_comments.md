# 毕业评价

配置来源：`world/graduation_comments.json`。

当游戏处于算法模式，或文言文结业总结的 LLM 调用失败、返回空内容时，后端会根据最终累计 GPA 从该文件选择一段毕业典礼评价，避免毕业页只显示单句占位符。

## 分支规则

当前默认分支：

| GPA 区间 | 说明 |
| -------- | ---- |
| `gpa >= 4.5` | 顶尖成绩评价 |
| `4.0 <= gpa < 4.5` | 稳健优秀评价 |
| `3.5 <= gpa < 4.0` | 平凡但完成学业评价 |
| `gpa < 3.5` | 低绩点反思评价 |

每个分支使用 `paragraphs` 数组保存多段文本。后端会用空行拼接段落。

## 维护方式

普通文案调整只需要编辑 `zjus-backend/world/graduation_comments.json`，不需要数据库迁移、OpenAPI 生成或前端类型生成。

修改后建议运行：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe -m pytest tests\unit\test_graduation_comments.py
```

若新增字段或改变分支结构，需要同步检查 `app/core/llm.py` 中的 `fallback_wenyan_report()`。
