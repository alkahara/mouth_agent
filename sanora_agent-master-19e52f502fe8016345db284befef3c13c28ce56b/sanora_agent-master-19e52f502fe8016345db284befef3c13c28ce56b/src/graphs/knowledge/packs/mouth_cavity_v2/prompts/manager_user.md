# 当前流程: {{flow_name}}

# 需要收集的槽位

{{slots}}

# 已收集槽位

{{slots_summary}}

# 当前待收集槽位

**{{pending_slot}}**

请判断用户的回答是否包含该槽位的有效信息。

# 对话历史

{{conversation_history}}

# 用户最新消息

{{user_message}}

# 你的任务

分析用户最新消息，提取槽位信息。

1. **判断用户回答是否针对当前待收集槽位 `{{pending_slot}}`**
2. **提取槽位值**：
   - 对于 `cause_trigger`（诱因）：
     - "没有"/"无"/"不知道" → 值为 `"none"`
     - 如果提到具体诱因 → 原样记录
   - 对于 `latest_time`（术后时间）：
     - 提取时间描述，保持原文
   - 对于其他槽位：分析用户回答，提取对应值
3. **识别患者情绪**：`anxious`/`calm`/`urgent`

**注意**：如果用户回答"没有"/"无"，`slot_valid` 应为 `true`，`value` 应为 `"none"`
