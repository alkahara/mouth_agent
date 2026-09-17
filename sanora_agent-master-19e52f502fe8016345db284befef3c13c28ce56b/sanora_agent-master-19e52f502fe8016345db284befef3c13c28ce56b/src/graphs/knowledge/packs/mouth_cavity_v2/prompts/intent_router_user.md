# 当前状态

- 当前 Flow: {{current_flow_id}}（{{current_flow_name}}）
- 待收集槽位: {{pending_slot}}
- 分诊流程状态: {{triage_status}}

# 对话历史

{{conversation_history}}

# 用户最新消息

{{user_message}}

# 你的任务

判断用户最新消息的意图类型。

**重要**：当前分诊流程状态是「{{triage_status}}」

- 如果状态是「已完成，RAG 问答模式」：
  - 用户问题**与口腔术后相关**（出血、护理、饮食、疼痛、症状、药物、就医等）→ `flow_related`
  - 用户问题**与口腔无关**（闲聊、身份询问、能力询问、无关话题如"你有妈妈吗"）→ `general_query`

- 如果状态是「进行中，槽位收集模式」：
  - 用户在回答当前 flow 的问题 → `flow_related`
  - 用户提到其他症状/问题 → 检查是否触发其他 flow → `flow_switch`
  - 通用问题（身份、能力、闲聊）→ `general_query`
