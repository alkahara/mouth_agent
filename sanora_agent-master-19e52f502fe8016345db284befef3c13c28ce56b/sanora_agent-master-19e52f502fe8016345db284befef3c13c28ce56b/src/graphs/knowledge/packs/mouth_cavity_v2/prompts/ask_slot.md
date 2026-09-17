# 任务

根据以下信息生成一个友好、专业的问题来收集槽位信息。

# 当前流程: {{flow_name}}

# 槽位信息

- **槽位名称**: {{slot_id}}
- **槽位描述**: {{slot_description}}
- **问题模板**: {{question_template}}
{% if options %}
- **可选项**: 
{% for opt in options %}
  - {{opt.key}}. {{opt.label}}
{% endfor %}
{% endif %}

# 患者情绪: {{patient_emotion}}

{% if patient_emotion == 'anxious' %}
**注意**: 患者当前比较焦虑，请先表达共情再提问。
{% endif %}

# 已收集信息摘要

{{slots_summary}}

# 要求

1. 如果患者焦虑（anxious），先表达共情再提问
2. 问题要简洁明了，避免过于专业的术语
3. 如果有选项，以选择题形式呈现
4. 使用问题模板作为基础，但可以根据上下文微调
5. 语气要亲切、专业

# 输出

直接输出问题内容（不需要 JSON 格式），例如：
"请问出血发生在术后多久？例如：术后12小时、3天、一周等。"
