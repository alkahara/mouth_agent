# 前端接入槽位信息指南

> 文档更新日期: 2025-12-29

本文档说明如何在前端接入口腔分诊系统的槽位信息展示功能。

## 一、开启 Debug 模式

要获取槽位信息，前端发送请求时需要在 `ChatRequest` 中设置 `debug_mode: true`：

```json
POST /v1/chat/completions
{
  "model": "...",
  "messages": [...],
  "stream": true,
  "debug_mode": true
}
```

**注意**：槽位信息仅在 `debug_mode: true` 时返回，生产环境可关闭以减少数据传输。

---

## 二、返回的数据格式

开启 debug 模式后，前端会通过 SSE 收到两种额外的数据：

### 2.1 实时槽位更新 (`slot_update`)

**触发时机**：每次用户回答问题后，state 更新时

```json
{
  "id": "chatcmpl-xxx",
  "choices": [{
    "index": 0,
    "delta": {
      "additional_kwargs": {
        "slot_update": {
          "cause_trigger": "has_trigger",
          "latest_time": "early",
          "surgery_type": "vascular",
          "bleeding_severity": "active"
        }
      }
    },
    "finish_reason": null
  }]
}
```

**用途**：用于展示槽位收集进度条或实时状态卡片。

### 2.2 最终诊断结果 (`triage_result`)

**触发时机**：分诊完成，输出最终护理建议时

```json
{
  "id": "chatcmpl-xxx",
  "choices": [{
    "index": 0,
    "delta": {
      "content": "根据您的情况...",
      "additional_kwargs": {
        "triage_result": {
          "risk_level": "medium",
          "care_plan_id": "active_bleed_standard",
          "slots": {
            "cause_trigger": "has_trigger",
            "latest_time": "rebleed",
            "surgery_type": "vascular",
            "bleeding_severity": "active",
            "can_compress": "can"
          }
        }
      }
    },
    "finish_reason": null
  }]
}
```

**用途**：用于展示风险等级卡片和诊断详情。

---

## 三、字段说明

### 3.1 槽位字段 (`slot_update` / `slots`)

| 字段 | 可能的值 | 说明 |
|------|---------|------|
| `cause_trigger` | `has_trigger` / `no_trigger` | 是否有诱因 |
| `latest_time` | `early` / `rebleed` / `late` | 时间分期 |
| `surgery_type` | `vascular` / `non_vascular` | 手术类型 |
| `bleeding_severity` | `minor` / `active` / `floor` | 出血程度 |
| `bleeding_location` | `lingual` / `palatal` | 出血部位 |
| `can_compress` | `can` / `cannot` / `no_gauze` / `tried_but_bleeding` | 压迫状态 |
| `symptom_description` | `has_symptom` / 其他 | 伴随症状 |
| `rebleed_after_compression` | `resolved` / `again` | 压迫后状态 |

### 3.2 诊断结果字段 (`triage_result`)

| 字段 | 可能的值 | 说明 |
|------|---------|------|
| `risk_level` | `none` / `low` / `medium` / `high` | 风险等级 |
| `care_plan_id` | 如 `mild_oze_early`, `active_bleed_standard` | 护理方案ID |
| `slots` | 对象 | 所有已收集的槽位值（不含 `_raw` 字段） |

### 3.3 风险等级对照表

| 值 | 含义 | 建议颜色 |
|----|------|---------|
| `none` | 无风险 | 🟢 绿色 `#4CAF50` |
| `low` | 低风险 | 🟢 浅绿 `#8BC34A` |
| `medium` | 中风险 | 🟡 黄色 `#FFC107` |
| `high` | 高风险 | 🔴 红色 `#F44336` |

---

## 四、前端解析代码示例

### 4.1 JavaScript / TypeScript 示例

```typescript
interface SlotUpdate {
  cause_trigger?: string;
  latest_time?: string;
  surgery_type?: string;
  bleeding_severity?: string;
  bleeding_location?: string;
  can_compress?: string;
  symptom_description?: string;
  rebleed_after_compression?: string;
  risk_level?: string;
  care_plan_id?: string;
}

interface TriageResult {
  risk_level: 'none' | 'low' | 'medium' | 'high';
  care_plan_id: string;
  slots: SlotUpdate;
}

// 状态管理
let collectedSlots: SlotUpdate = {};
let triageResult: TriageResult | null = null;

// SSE 解析（假设使用 fetch + ReadableStream）
async function streamChat(messages: any[]) {
  const response = await fetch('/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer YOUR_API_KEY'
    },
    body: JSON.stringify({
      messages,
      stream: true,
      debug_mode: true  // 开启 debug 模式
    })
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(line => line.startsWith('data: '));

    for (const line of lines) {
      const jsonStr = line.slice(6); // 移除 "data: " 前缀
      if (jsonStr === '[DONE]') continue;

      try {
        const data = JSON.parse(jsonStr);
        handleSSEData(data);
      } catch (e) {
        console.error('Parse error:', e);
      }
    }
  }
}

function handleSSEData(data: any) {
  const delta = data.choices?.[0]?.delta;
  if (!delta) return;

  // 处理文本内容
  if (delta.content) {
    appendMessage(delta.content);
  }

  // 处理 additional_kwargs
  if (delta.additional_kwargs) {
    const kwargs = delta.additional_kwargs;

    // 方案 B：实时槽位更新
    if (kwargs.slot_update) {
      collectedSlots = { ...collectedSlots, ...kwargs.slot_update };
      updateSlotProgressUI(collectedSlots);
    }

    // 方案 A：最终诊断结果
    if (kwargs.triage_result) {
      triageResult = kwargs.triage_result;
      showTriageResultCard(triageResult);
    }
  }
}

// UI 更新函数
function updateSlotProgressUI(slots: SlotUpdate) {
  const slotNames = [
    'cause_trigger', 'latest_time', 'surgery_type',
    'bleeding_severity', 'can_compress'
  ];
  const total = slotNames.length;
  const filled = slotNames.filter(name => slots[name as keyof SlotUpdate]).length;

  // 更新进度条
  const progress = (filled / total) * 100;
  const progressEl = document.getElementById('slot-progress');
  if (progressEl) {
    progressEl.style.width = `${progress}%`;
  }

  // 更新槽位列表
  slotNames.forEach(name => {
    const el = document.getElementById(`slot-${name}`);
    if (el) {
      const value = slots[name as keyof SlotUpdate];
      el.className = value ? 'slot-filled' : 'slot-empty';
      el.textContent = value || '待收集';
    }
  });
}

function showTriageResultCard(result: TriageResult) {
  const riskColors: Record<string, string> = {
    none: '#4CAF50',
    low: '#8BC34A',
    medium: '#FFC107',
    high: '#F44336'
  };

  const riskLabels: Record<string, string> = {
    none: '无风险',
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  };

  const card = document.getElementById('triage-card');
  if (!card) return;

  card.style.borderColor = riskColors[result.risk_level];
  card.innerHTML = `
    <div class="risk-badge" style="background: ${riskColors[result.risk_level]}">
      ${riskLabels[result.risk_level]}
    </div>
    <div class="triage-details">
      <p>护理方案: ${result.care_plan_id}</p>
      <ul>
        ${Object.entries(result.slots).map(([k, v]) =>
          `<li>${formatSlotName(k)}: ${formatSlotValue(k, v)}</li>`
        ).join('')}
      </ul>
    </div>
  `;
  card.style.display = 'block';
}

function formatSlotName(key: string): string {
  const names: Record<string, string> = {
    cause_trigger: '诱因',
    latest_time: '时间分期',
    surgery_type: '手术类型',
    bleeding_severity: '出血程度',
    bleeding_location: '出血部位',
    can_compress: '压迫状态',
    symptom_description: '伴随症状',
    rebleed_after_compression: '压迫后状态'
  };
  return names[key] || key;
}

function formatSlotValue(key: string, value: string): string {
  const valueMap: Record<string, Record<string, string>> = {
    latest_time: { early: '术后<24h', rebleed: '术后24h~5天', late: '术后>5天' },
    surgery_type: { vascular: '涉血管手术', non_vascular: '常规手术' },
    bleeding_severity: { minor: '轻微渗血', active: '活动性出血', floor: '口底血肿' },
    can_compress: { can: '可压迫', cannot: '无法压迫', no_gauze: '无纱布', tried_but_bleeding: '压迫后仍出血' },
    cause_trigger: { has_trigger: '有诱因', no_trigger: '无诱因' },
    rebleed_after_compression: { resolved: '已止血', again: '仍出血' },
    bleeding_location: { lingual: '舌侧', palatal: '腭侧' }
  };
  return valueMap[key]?.[value] || value;
}

function appendMessage(text: string) {
  // 实现消息追加逻辑
  console.log('Message:', text);
}
```

### 4.2 Vue 3 示例

```vue
<template>
  <div class="triage-info">
    <!-- 槽位收集进度 -->
    <div class="slot-progress" v-if="hasSlots">
      <h4>信息收集进度</h4>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
      </div>
      <div class="slot-tags">
        <span
          v-for="slot in slotNames"
          :key="slot"
          :class="['slot-tag', collectedSlots[slot] ? 'filled' : 'empty']"
        >
          {{ formatSlotName(slot) }}
          <span v-if="collectedSlots[slot]">✓</span>
        </span>
      </div>
    </div>

    <!-- 诊断结果卡片 -->
    <div
      v-if="triageResult"
      class="triage-card"
      :class="'risk-' + triageResult.risk_level"
    >
      <div class="risk-badge" :style="{ background: riskColors[triageResult.risk_level] }">
        {{ riskLabels[triageResult.risk_level] }}
      </div>
      <div class="details">
        <p><strong>护理方案:</strong> {{ triageResult.care_plan_id }}</p>
        <ul>
          <li v-for="(value, key) in triageResult.slots" :key="key">
            {{ formatSlotName(key as string) }}: {{ formatSlotValue(key as string, value as string) }}
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';

interface SlotUpdate {
  [key: string]: string | undefined;
}

interface TriageResult {
  risk_level: 'none' | 'low' | 'medium' | 'high';
  care_plan_id: string;
  slots: SlotUpdate;
}

const collectedSlots = ref<SlotUpdate>({});
const triageResult = ref<TriageResult | null>(null);

const slotNames = ['cause_trigger', 'latest_time', 'surgery_type', 'bleeding_severity', 'can_compress'];

const riskColors: Record<string, string> = {
  none: '#4CAF50',
  low: '#8BC34A',
  medium: '#FFC107',
  high: '#F44336'
};

const riskLabels: Record<string, string> = {
  none: '🟢 无风险',
  low: '🟢 低风险',
  medium: '🟡 中风险',
  high: '🔴 高风险'
};

const hasSlots = computed(() => Object.keys(collectedSlots.value).length > 0);

const progressPercent = computed(() => {
  const filled = slotNames.filter(s => collectedSlots.value[s]).length;
  return (filled / slotNames.length) * 100;
});

// 处理 SSE 消息 - 在父组件中调用
function handleSSEData(data: any) {
  const delta = data.choices?.[0]?.delta;
  if (!delta?.additional_kwargs) return;

  if (delta.additional_kwargs.slot_update) {
    collectedSlots.value = {
      ...collectedSlots.value,
      ...delta.additional_kwargs.slot_update
    };
  }

  if (delta.additional_kwargs.triage_result) {
    triageResult.value = delta.additional_kwargs.triage_result;
  }
}

function formatSlotName(key: string): string {
  const names: Record<string, string> = {
    cause_trigger: '诱因',
    latest_time: '时间分期',
    surgery_type: '手术类型',
    bleeding_severity: '出血程度',
    bleeding_location: '出血部位',
    can_compress: '压迫状态',
  };
  return names[key] || key;
}

function formatSlotValue(key: string, value: string): string {
  const valueMap: Record<string, Record<string, string>> = {
    latest_time: { early: '术后<24h', rebleed: '术后24h~5天', late: '术后>5天' },
    surgery_type: { vascular: '涉血管手术', non_vascular: '常规手术' },
    bleeding_severity: { minor: '轻微渗血', active: '活动性出血', floor: '口底血肿' },
    can_compress: { can: '可压迫', cannot: '无法压迫', no_gauze: '无纱布' },
    bleeding_location: { lingual: '舌侧', palatal: '腭侧' }
  };
  return valueMap[key]?.[value] || value;
}

// 暴露给父组件使用
defineExpose({ handleSSEData });
</script>

<style scoped>
.triage-card {
  padding: 16px;
  border-radius: 8px;
  border-left: 4px solid;
  background: #f9f9f9;
  margin-top: 16px;
}

.risk-none, .risk-low { border-left-color: #4CAF50; }
.risk-medium { border-left-color: #FFC107; }
.risk-high { border-left-color: #F44336; }

.risk-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 4px;
  color: white;
  font-weight: bold;
  margin-bottom: 12px;
}

.progress-bar {
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4CAF50, #8BC34A);
  transition: width 0.3s ease;
}

.slot-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.slot-tag {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.slot-tag.filled {
  background: #e8f5e9;
  color: #2e7d32;
}

.slot-tag.empty {
  background: #f5f5f5;
  color: #9e9e9e;
}
</style>
```

---

## 五、数据流总结

```
┌──────────────┐    POST /v1/chat/completions     ┌──────────────┐
│    前端      │  ────────────────────────────▶  │    后端      │
│              │    { debug_mode: true }          │              │
└──────────────┘                                  └──────────────┘
       ▲                                                 │
       │                                                 │
       │  SSE: slot_update (每次 state 变化)              │
       │  SSE: triage_result (最终诊断时)                 │
       └─────────────────────────────────────────────────┘
```

---

## 六、UI 设计参考

### 6.1 槽位收集进度条

```
收集进度：████████░░ 80%
✓ 诱因  ✓ 时间  ✓ 症状  ✓ 术式  ○ 出血程度  ○ 压迫情况
```

### 6.2 风险等级卡片

```
┌─────────────────────────────────────┐
│  🔴 高风险 / 🟡 中风险 / 🟢 低风险    │
├─────────────────────────────────────┤
│  诊断详情                            │
│  • 手术时间：术后24小时内             │
│  • 手术类型：上颌窦外提升植骨术        │
│  • 出血程度：活动性出血               │
│  • 出血部位：舌侧                     │
│  • 压迫状态：可压迫                   │
│  • 护理方案：active_bleed_early       │
└─────────────────────────────────────┘
```

---

## 七、注意事项

1. **仅在 debug 模式下返回槽位信息**：生产环境可根据需要决定是否开启
2. **slot_update 可能多次触发**：前端应使用合并策略更新状态
3. **triage_result 仅在分诊完成时返回一次**：与最终的文本回复一起返回
4. **兼容性**：如果未开启 debug 模式，`additional_kwargs` 中不会包含这些字段

---

*本文档由 AI 生成，如有问题请反馈修正。*
