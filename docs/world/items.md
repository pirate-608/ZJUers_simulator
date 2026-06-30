# 道具设定

配置来源：`world/items.json`。

道具系统由“金币 + 背包 + 持有即生效加成”组成。玩家在游戏中栏的“道具”标签页购买或出售道具；道具加成会作为 effective stats 参与显示、结算、考试、Game Over 和 LLM 上下文，但不会反复写回基础属性。

## 经济参数

| 字段 | 当前值 | 说明 |
| ---- | ------ | ---- |
| `economy.initial_gold` | 120 | 新游戏初始金币 |
| `exam_income.base` | 20 | 期末金币基础收入 |
| `exam_income.gpa_multiplier` | 36 | 当期 GPA 收入系数 |
| `exam_income.pass_all_bonus` | 30 | 全科通过奖励 |
| `exam_income.failed_penalty_per_course` | 24 | 每门挂科扣减 |
| `exam_income.min` / `max` | 0 / 240 | 单次期末收入上下限 |

## 当前道具

| ID | 名称 | 分类 | 价格 | 出售价 | 标签 | 效果 |
| --- | --- | --- | --- | --- | --- | --- |
| `qiushi_planner` | 求是日程本 | 学习 | 90 | 45 | 学习、规划 | IQ +4，压力 -3 |
| `blue_lake_thermos` | 瑞幸咖啡券 | 生活 | 70 | 35 | 生活、精力 | 精力 +8，心态 +2 |
| `cc98_archive_key` | CC98 旧帖索引 | 社交 | 110 | 55（默认） | 社交、论坛 | EQ +5，魅力 +3，声望 +3 |
| `silent_library_pass` | 图书馆预约脚本 | 学习 | 130 | 65 | 学习、效率 | IQ +6，效率 +5，压力 +2 |
| `campus_bike_coupon` | 校园单车月卡 | 生活 | 85 | 42 | 生活、通勤 | 精力 +5，压力 -5 |
| `club_badge` | cc98 联名雨伞 | 社交 | 100 | 50 | 社交、声望 | EQ +4，魅力 +5，声望 +6 |
| `lucky_canteen_card` | 幸运饭卡贴 | 玄学 | 75 | 37 | 玄学、运气 | 运气 +7 |
| `academy_fountain_pen` | 学院派钢笔 | 学习 | 150 | 75 | 学习、声望 | IQ +5，声望 +5，心态 +2 |
| `past_exam_paper` | 历年卷网盘 | 学习 | 60 | 30 | 学习、考试 | IQ +3，效率 +5 |
| `savia_external_brain` | Savia 的外装代脑 | 学习 | 100 | 50 | 学习、考试 | IQ +8，压力 -2，效率 +4 |
| `laptop_stand` | 电脑支架 | 生活 | 40 | 20 | 生活、学习 | 效率 +3 |
| `gpt_plus_subscription` | GPT Plus 永久订阅 | 生活 | 250 | 125 | 生活、学习 | IQ +10，效率 +10，压力 -8 |
| `magic_turtle` | 神奇小龟 | 生活 | 100 | 50 | 生活 | 效率 +5，魅力 +2 |

## 运行规则

- 每个 `item_id` 同一时间最多拥有一件；出售后可再次购买。
- `sell_price` 可显式配置；缺省时按价格 50% 计算。
- 购买和出售只通过 WebSocket `item_buy` / `item_sell`，不进入 OpenAPI。
- 暂停或新手引导期间可以浏览和搜索道具，但不能购买或出售。
- `effects` 字段必须在[属性定义](/world/stat_definitions)中允许 `allow_item_effect=true`。
- 配置非法时后端会把道具目录降级为空并记录日志，避免游戏启动失败。

## 维护入口

普通道具新增、调价或改效果可通过 `/admin/items` 后台页面保存并热重载，也可以直接编辑 `zjus-backend/world/items.json` 后运行世界数据校验。完整开发流程见[游戏设定维护](/dev/world-data)。
