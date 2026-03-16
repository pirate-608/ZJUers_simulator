## 【generate_cc98_post】
玩家当前状态：{json.dumps(player_stats, ensure_ascii=False)}
你正在模拟浙江大学CC98论坛的帖子列表。

请生成 5 条简短、有趣、符合大学生网络用语的帖子标题/内容。
要求：
1. 第一条内容必须与主题“{trigger}”相关（效果：{effect}）。
2. 剩下的 4 条可以是随机的校园日常话题（吐槽、求助、分享等），越丰富越好，避免重复单调的关键词（如在多个帖子里反复提及“GPA”等）。
3. 请严格输出 JSON 格式，结构如下：
```json
{
    "posts": ["帖子内容1", "帖子内容2", "帖子内容3", "帖子内容4", "帖子内容5"]
}
```

## 【generate_random_event】
玩家当前状态：{json.dumps(player_stats, ensure_ascii=False)}
你是一个文字模拟游戏的上帝系统。浙大学生。
{history_hint}
请生成 3 个突发的校园随机事件。要求风格诡异：包含学习压力、社团社交、校园传说、校园恋爱、惊险事故、狼人瞬间或生活小插曲。
严禁与上方“近期已发生事件”雷同。
每个事件应包含两个选项，会对玩家状态产生合理影响（-10 到 +10）。

## 【generate_dingtalk_message】
玩家当前状态：{json.dumps(player_stats, ensure_ascii=False)}
你正在模拟浙江大学的“钉钉”消息通知。浙大学生。
触发场景：{context}。
请批量生成 5 条不同的钉钉消息。
要求：内容要真实（包含通知、约饭、求助、催作业等），发送人身份要切换。
请严格输出 JSON 格式：

```json
{
    "messages": [
        {
            "sender": "发送人",
            "role": "counselor/student/system/teacher",
            "content": "内容（30字以内）",
            "is_urgent": false
        },
        ... (重复 5 条)
    ]
}
```

## 【generate_wenyan_report】
玩家数据：{json.dumps(final_stats, ensure_ascii=False)}
你是一位古风文案大师。请根据以上玩家的折姜大学结业数据，为其撰写一段100字左右的文言文结业总结，内容需涵盖其专业、能力、GPA、性格、成就等主要信息，风格典雅、用词考究，严肃中不失诙谐风趣，结尾可有调侃或祝福。
只需返回文言文内容本身，不要任何解释。