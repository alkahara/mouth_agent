<template>
  <div class="h-screen flex flex-col overflow-hidden">
    <header class="shrink-0 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
      <div class="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
        <div class="flex items-center gap-4">
          <img alt="Agent logo" src="../assets/logo.svg" class="h-10 w-10" />
          <div>
            <h1 class="text-lg font-semibold text-white">AI Agent 对话</h1>
            <p class="text-sm text-slate-400">连接本地 Agent 服务，快速验证对话逻辑。</p>
          </div>
        </div>

        <div class="ml-auto flex items-center gap-3">
          <div class="flex flex-col items-end text-right">
            <span class="text-xs uppercase tracking-wide text-slate-500">当前 Agent</span>
            <span class="text-sm font-medium text-slate-200">{{ selectedAgentLabel }}</span>
          </div>
          <div class="relative">
            <select
              v-model="selectedAgent"
              :disabled="isLoading"
              class="appearance-none rounded-lg border border-slate-700 bg-slate-800/90 px-4 py-2 pr-10 text-sm text-slate-100 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:opacity-70"
            >
              <option v-for="option in agentOptions" :key="option.key" :value="option.key">
                {{ option.label }}
              </option>
            </select>
            <svg
              class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 10.94l3.71-3.71a.75.75 0 111.06 1.06l-4.24 4.24a.75.75 0 01-1.06 0L5.21 8.29a.75.75 0 01.02-1.08z"
                clip-rule="evenodd"
              />
            </svg>
          </div>
          <button
            type="button"
            class="rounded-lg border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400"
            :class="
              debugEnabled
                ? 'border-sky-400/60 bg-slate-800 text-sky-200 shadow-[0_0_15px_rgba(56,189,248,0.35)]'
                : 'border-slate-700 bg-slate-900 text-slate-400'
            "
            :disabled="isLoading"
            @click="toggleDebug"
          >
            <span class="block text-[10px]">Debug</span>
            <span class="text-base normal-case">{{ debugEnabled ? '开启' : '关闭' }}</span>
          </button>
          <button
            type="button"
            class="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-2 text-sm text-slate-300 transition hover:bg-slate-700 hover:text-white"
            @click="handleLogout"
          >
            退出
          </button>
        </div>
      </div>
    </header>

    <main class="flex-1 min-h-0 py-6">
      <div class="max-w-5xl mx-auto h-full px-4 lg:px-6 flex flex-col gap-4">
        <!-- 顶部：槽位收集进度卡片 (仅口腔 Agent debug 模式下显示) -->
        <div v-if="debugEnabled && isMouthAgent" class="shrink-0 rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
          <div class="flex flex-wrap items-start gap-6">
            <!-- 左侧：进度信息 -->
            <div class="flex-1 min-w-[200px]">
              <div class="flex items-center gap-2 mb-3">
                <svg class="w-4 h-4 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 class="text-sm font-semibold text-white">槽位收集进度</h3>
                <span class="ml-auto text-xs text-slate-400">{{ filledSlotCount }} / {{ SLOT_NAMES.length }} 项 ({{ Math.round(slotProgressPercent) }}%)</span>
              </div>

              <!-- 进度条 -->
              <div class="h-2 bg-slate-700 rounded-full overflow-hidden mb-3">
                <div
                  class="h-full bg-gradient-to-r from-sky-500 to-emerald-400 transition-all duration-500 ease-out"
                  :style="{ width: slotProgressPercent + '%' }"
                ></div>
              </div>

              <!-- 槽位标签 -->
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="slotName in SLOT_NAMES"
                  :key="slotName"
                  class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-colors"
                  :class="collectedSlots[slotName] ? 'bg-emerald-900/40 text-emerald-300 border border-emerald-700/50' : 'bg-slate-700/50 text-slate-500 border border-slate-600/30'"
                >
                  <svg
                    v-if="collectedSlots[slotName]"
                    class="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                  </svg>
                  <span class="w-1.5 h-1.5 rounded-full bg-slate-500" v-else></span>
                  {{ formatSlotName(slotName) }}
                  <span v-if="collectedSlots[slotName]" class="text-emerald-400/80 font-medium">: {{ formatSlotValue(slotName, String(collectedSlots[slotName])) }}</span>
                </span>
              </div>
            </div>

            <!-- 右侧：风险等级卡片 -->
            <div
              v-if="triageResult"
              class="shrink-0 rounded-xl p-4 border-l-4 min-w-[180px] transition-colors"
              :style="{
                borderLeftColor: RISK_COLORS[triageResult.risk_level] || '#64748b',
                backgroundColor: 'rgba(30, 41, 59, 0.7)'
              }"
            >
              <div class="flex items-center gap-2 mb-2">
                <span
                  class="inline-block px-2.5 py-1 rounded-md text-xs font-bold text-white"
                  :style="{ backgroundColor: RISK_COLORS[triageResult.risk_level] || '#64748b' }"
                >
                  {{ RISK_LABELS[triageResult.risk_level] || triageResult.risk_level }}
                </span>
              </div>
              <p class="text-xs text-slate-400 mb-1">护理方案</p>
              <p class="text-sm font-medium text-slate-200 font-mono">{{ triageResult.care_plan_id }}</p>
            </div>
          </div>
        </div>

        <!-- 聊天区域 + 预设问题侧边栏 -->
        <div class="grid flex-1 min-h-0 gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <!-- 聊天区域 -->
          <div
            ref="scrollContainer"
            class="h-full min-h-0 space-y-4 overflow-y-auto pr-1 pb-4 lg:pr-4"
          >
            <div v-for="msg in messages" :key="msg.id" class="space-y-2">
              <div
                v-if="debugEnabled && getDebugFinalJudgment(msg)"
                class="max-w-3xl mx-auto px-4 !my-1"
              >
                <div class="rounded-lg bg-orange-950/30 border border-orange-800/40 px-3 py-2 text-xs text-orange-200/90 font-mono shadow-sm">
                  <div class="flex items-center gap-1.5 mb-1 opacity-60 text-[10px] tracking-wider uppercase">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    <span>Decision Logic</span>
                  </div>
                  <div class="leading-relaxed">
                    {{ getDebugFinalJudgment(msg) }}
                  </div>
                </div>
              </div>
              <MessageBubble :role="msg.role" :timestamp="msg.timestamp">
                {{ msg.text }}
              </MessageBubble>
              <div v-if="msg.videoUrl" class="max-w-3xl mx-auto px-4 !my-3">
                <div class="rounded-xl overflow-hidden bg-slate-900 border border-slate-700/60 shadow-lg">
                  <div v-if="extractYoukuId(msg.videoUrl)" class="aspect-video w-full relative">
                    <iframe
                      :src="`https://player.youku.com/embed/${extractYoukuId(msg.videoUrl)}`"
                      class="absolute inset-0 w-full h-full"
                      frameborder="0"
                      allowfullscreen
                    ></iframe>
                  </div>
                  <div v-else class="p-4 flex items-center gap-3">
                    <div class="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center shrink-0">
                      <svg class="w-5 h-5 text-sky-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div class="flex-1 min-w-0">
                      <h4 class="text-sm font-medium text-slate-200">相关视频教程</h4>
                      <p class="text-xs text-slate-500 truncate">{{ msg.videoUrl }}</p>
                    </div>
                    <a
                      :href="msg.videoUrl"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium text-white transition"
                    >
                      观看视频
                    </a>
                  </div>
                  <div v-if="msg.videoPassword" class="px-4 py-2 bg-slate-800/50 border-t border-slate-700/40 flex items-center gap-2">
                      <svg class="w-3.5 h-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                      </svg>
                      <span class="text-xs text-slate-400">视频密码：</span>
                      <code class="text-xs font-mono font-medium text-sky-300 bg-sky-900/20 px-1.5 py-0.5 rounded">{{ msg.videoPassword }}</code>
                  </div>
                </div>
              </div>

              <div
                v-if="msg.role === 'assistant' && msg.options && msg.options.length > 0"
                class="max-w-3xl mx-auto px-4"
              >
                <!-- Multi-select header with count -->
                <div
                  v-if="msg.optionsConfig?.multiSelect"
                  class="flex items-center justify-between mb-3 text-sm text-slate-400"
                >
                  <span>
                    已选择 {{ msg.selectedOptions?.size || 0 }}
                    <template v-if="msg.optionsConfig?.maxSelect">
                      / {{ msg.optionsConfig.maxSelect }}
                    </template>
                    项
                  </span>
                  <span v-if="msg.optionsConfig?.maxSelect" class="text-xs text-slate-500">
                    最多选择 {{ msg.optionsConfig.maxSelect }} 项
                  </span>
                </div>

                <!-- Options grid -->
                <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  <button
                    v-for="option in msg.options"
                    :key="`${msg.id}-${option.key}`"
                    type="button"
                    :class="[
                      'group relative overflow-hidden rounded-2xl border text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:cursor-not-allowed disabled:opacity-60',
                      option.imageUrl ? 'p-3' : 'px-4 py-3',
                      isOptionSelected(msg, option.key)
                        ? 'border-sky-400 bg-sky-900/40 ring-2 ring-sky-400/50'
                        : 'border-slate-700/70 bg-slate-900/80 hover:border-sky-400/60 hover:bg-slate-800/80',
                      isOptionDisabled(msg, option.key) ? 'opacity-50 cursor-not-allowed' : ''
                    ]"
                    :disabled="isLoading || (msg.agent && msg.agent !== selectedAgent) || isOptionDisabled(msg, option.key)"
                    @click="handleOptionClick(msg, option)"
                  >
                    <!-- Selection indicator for multi-select -->
                    <div
                      v-if="msg.optionsConfig?.multiSelect"
                      class="absolute top-2 right-2 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors"
                      :class="isOptionSelected(msg, option.key)
                        ? 'border-sky-400 bg-sky-400'
                        : 'border-slate-500 bg-slate-800'"
                    >
                      <svg
                        v-if="isOptionSelected(msg, option.key)"
                        class="w-3 h-3 text-white"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <div v-if="option.imageUrl" class="aspect-video w-full overflow-hidden rounded-xl bg-slate-800/70">
                      <img
                        :src="option.imageUrl"
                        :alt="option.label"
                        class="h-full w-full object-cover transition duration-200 ease-out group-hover:scale-[1.02]"
                        loading="lazy"
                      />
                    </div>
                    <div :class="[
                      option.imageUrl ? 'mt-2 text-sm font-medium' : 'text-sm font-medium',
                      isOptionSelected(msg, option.key) ? 'text-sky-200' : 'text-slate-200'
                    ]">
                      <span class="font-semibold text-sky-400 mr-1">{{ option.key }}.</span>
                      {{ option.label }}
                    </div>
                  </button>
                </div>

                <!-- Confirm button for multi-select -->
                <div
                  v-if="msg.optionsConfig?.multiSelect"
                  class="mt-4 flex justify-end"
                >
                  <button
                    type="button"
                    class="rounded-xl border border-sky-500 bg-sky-600 px-6 py-2.5 text-sm font-medium text-white transition hover:bg-sky-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="isLoading || !msg.selectedOptions?.size || (msg.agent && msg.agent !== selectedAgent)"
                    @click="handleMultiSelectConfirm(msg)"
                  >
                    {{ msg.optionsConfig?.confirmButtonText || '确认选择' }}
                    <span v-if="msg.selectedOptions?.size" class="ml-1 opacity-80">
                      ({{ msg.selectedOptions.size }})
                    </span>
                  </button>
                </div>
              </div>
            </div>

            <div v-if="isLoading" class="max-w-3xl mx-auto px-4 py-3">
              <div class="inline-flex items-center gap-2 rounded-full bg-slate-800/80 px-3 py-1 text-sm text-slate-300">
                <span class="h-2 w-2 rounded-full bg-sky-400 animate-pulse"></span>
                <span class="flex items-center">
                  正在等待 Agent 回复
                  <span class="loading-dots" aria-hidden="true">
                    <span></span>
                    <span></span>
                    <span></span>
                  </span>
                </span>
              </div>
            </div>

            <div v-if="error" class="max-w-3xl mx-auto px-4">
              <div class="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
                {{ error }}
              </div>
            </div>

            <div v-if="messages.length === 0 && !isLoading" class="max-w-3xl mx-auto px-4">
              <div class="rounded-2xl border border-dashed border-slate-700 bg-slate-800/40 px-6 py-6 text-center text-sm text-slate-400">
                输入内容开始与 Agent 对话。
              </div>
            </div>
          </div>

          <!-- 右侧边栏：预设问题 -->
          <aside class="hidden h-full w-[280px] flex-col gap-4 overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-4 lg:flex">
            <!-- 预设问题区域 -->
            <div class="shrink-0">
              <h2 class="text-base font-semibold text-white">预设问题</h2>
              <p class="mt-1 text-xs text-slate-400">点击即可快速提问</p>
            </div>
            <div v-if="isLoadingPresets" class="text-sm text-slate-400">
              正在加载预设问题...
            </div>
            <div v-else-if="presetError" class="text-sm text-rose-300">
              {{ presetError }}
            </div>
            <div v-else-if="presetQuestions.length === 0" class="text-sm text-slate-400">
              暂无预设问题。
            </div>
            <ul v-else class="flex flex-1 flex-col gap-2 overflow-y-auto">
              <li v-for="(question, index) in presetQuestions" :key="index">
                <button
                  type="button"
                  class="w-full rounded-xl border border-transparent bg-slate-800/70 px-3 py-2 text-left text-sm text-slate-200 transition hover:border-sky-400/60 hover:bg-slate-800 hover:text-sky-200"
                  :disabled="isLoading"
                  @click="handlePresetClick(question)"
                >
                  {{ question }}
                </button>
              </li>
            </ul>
          </aside>
        </div>
      </div>
    </main>

    <div class="shrink-0 border-t border-slate-800 bg-slate-900/95 backdrop-blur">
      <ChatInput
        ref="chatInputRef"
        :is-sending="isLoading"
        :show-reassess="selectedAgent === 'mouth' || selectedAgent === 'mouth_v2'"
        :can-reassess="canReassess"
        @submit="handleSubmit"
        @abort="handleAbort"
        @reassess="handleReassess"
      />
    </div>

    <!-- 其他表现输入对话框 -->
    <div
      v-if="showOtherInputDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      @click.self="handleOtherInputCancel"
    >
      <div class="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <h3 class="mb-2 text-lg font-semibold text-white">{{ otherInputDialogTitle }}</h3>
        <p class="mb-4 text-sm text-slate-400">{{ otherInputDialogHint }}</p>
        <textarea
          ref="otherInputTextarea"
          v-model="otherInputText"
          class="w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40"
          rows="4"
          :placeholder="otherInputPlaceholder"
          @keydown.enter.ctrl="handleOtherInputSubmit(otherInputText)"
          @keydown.esc="handleOtherInputCancel"
        ></textarea>
        <div class="mt-4 flex justify-end gap-3">
          <button
            type="button"
            class="rounded-lg border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-700 hover:text-white"
            @click="handleOtherInputCancel"
          >
            取消
          </button>
          <button
            type="button"
            class="rounded-lg border border-sky-500 bg-sky-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!otherInputText || !otherInputText.trim()"
            @click="handleOtherInputSubmit(otherInputText)"
          >
            提交
          </button>
        </div>
        <p class="mt-3 text-xs text-slate-500">提示：按 Ctrl+Enter 快速提交</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import ChatInput from "../components/ChatInput.vue";
import MessageBubble from "../components/MessageBubble.vue";
import request from "../utils/request";
import { removeToken } from "../utils/auth";

const router = useRouter();

type AgentKey = "disney" | "mouth" | "mouth_v2";

interface ChatOption {
  key: string;
  label: string;
  imageUrl?: string | null;
}

interface OptionsConfig {
  multiSelect: boolean;
  maxSelect: number | null;
  confirmButtonText: string;
}

// 口腔 Agent 槽位信息接口
interface SlotUpdate {
  is_surgical_area?: string;
  cause_trigger?: string;
  latest_time?: string;
  surgery_type?: string;
  bleeding_severity?: string;
  bleeding_location?: string;
  can_compress?: string;
  symptom_description?: string;
  rebleed_after_compression?: string;
  [key: string]: string | undefined;
}

interface TriageResult {
  risk_level: 'none' | 'low' | 'medium' | 'high';
  care_plan_id: string;
  slots: SlotUpdate;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: string;
  agent?: AgentKey;
  options?: ChatOption[];
  optionsConfig?: OptionsConfig;
  selectedOptions?: Set<string>; // For tracking multi-select state
  debugInfo?: Record<string, unknown>;
  videoUrl?: string;
  videoPassword?: string;
}

const messages = ref<ChatMessage[]>([]);
const isLoading = ref(false);
const error = ref<string | null>(null);
const currentRequest = ref<AbortController | null>(null);
const scrollContainer = ref<HTMLElement | null>(null);
const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null);
const presetQuestions = ref<string[]>([]);
const presetError = ref<string | null>(null);
const isLoadingPresets = ref(false);
const currentPresetRequest = ref<AbortController | null>(null);
const debugEnabled = ref(true);

const agentOptions: { key: AgentKey; label: string }[] = [
  { key: "disney", label: "迪士尼 Agent" },
  { key: "mouth_v2", label: "口腔 Agent V2" },
];

const selectedAgent = ref<AgentKey>("mouth_v2");
const DEFAULT_MOUTH_REASSESS_PROMPT = "请提供一条人文关怀话术";
const pendingAutoReassess = ref(false);
const hasReassessed = ref(false);
const showOtherInputDialog = ref(false);

// 兼容 HTTP 环境的 UUID 生成函数
const generateUUID = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    try {
      return crypto.randomUUID();
    } catch (e) {
      // 某些浏览器即便有函数，非安全上下文调用也可能抛错
    }
  }
  // Fallback for non-secure contexts
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

// 会话 UUID 管理 (用于 mouth_v2 agent 多会话支持)
const threadId = ref<string>(generateUUID());

// 生成新会话的辅助函数
const generateNewThreadId = () => {
  threadId.value = generateUUID();
  console.log('[Session] 新 thread_id:', threadId.value);
};
const pendingOtherOption = ref<{ messageId: string; option: ChatOption } | null>(null);
const otherInputText = ref("");
const otherInputTextarea = ref<HTMLTextAreaElement | null>(null);

// 口腔 Agent 槽位收集状态
const collectedSlots = ref<SlotUpdate>({});
const triageResult = ref<TriageResult | null>(null);

const lastMouthUserMessage = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index -= 1) {
    const entry = messages.value[index];
    if (entry.role === "user" && (entry.agent === "mouth" || entry.agent === "mouth_v2") && entry.text.trim().length > 0) {
      return entry;
    }
  }
  return null;
});

const canReassess = computed(
  () => (selectedAgent.value === "mouth" || selectedAgent.value === "mouth_v2") && Boolean(lastMouthUserMessage.value) && !hasReassessed.value,
);

const selectedAgentLabel = computed(() => {
  const found = agentOptions.find((option) => option.key === selectedAgent.value);
  return found ? found.label : "未选择";
});

const otherInputDialogTitle = computed(() => {
  const label = pendingOtherOption.value?.option.label;
  if (label === "其他表现") {
    return "请描述其他表现";
  } else if (label === "其他选择") {
    return "请描述其他选择";
  }
  return "请输入详细描述";
});

const otherInputDialogHint = computed(() => {
  const label = pendingOtherOption.value?.option.label;
  if (label === "其他表现") {
    return "请详细描述患者的具体表现";
  } else if (label === "其他选择") {
    return "请详细描述您的选择";
  }
  return "请详细描述";
});

const otherInputPlaceholder = computed(() => {
  const label = pendingOtherOption.value?.option.label;
  if (label === "其他表现") {
    return "例如：患者出现轻微肿胀...";
  } else if (label === "其他选择") {
    return "请输入您的选择...";
  }
  return "请输入...";
});


const extractYoukuId = (url: string): string | null => {
    // Matches id_XNjM4OTI1NjYwOA== pattern
    const match = url.match(/id_([a-zA-Z0-9=]+)/);
    return match ? match[1] : null;
};

// 槽位配置和辅助函数
const SLOT_NAMES = ['is_surgical_area', 'cause_trigger', 'latest_time', 'surgery_type', 'bleeding_severity', 'can_compress'] as const;

const SLOT_DISPLAY_NAMES: Record<string, string> = {
  is_surgical_area: '手术区域',
  cause_trigger: '诱因',
  latest_time: '时间分期',
  surgery_type: '手术类型',
  bleeding_severity: '出血程度',
  bleeding_location: '出血部位',
  can_compress: '压迫状态',
  symptom_description: '伴随症状',
  rebleed_after_compression: '压迫后状态',
};

const SLOT_VALUE_DISPLAY: Record<string, Record<string, string>> = {
  is_surgical_area: { yes: '是', no: '否' },
  latest_time: { early: '术后<24h', rebleed: '术后24h~5天', late: '术后>5天' },
  surgery_type: { vascular: '涉血管手术', non_vascular: '常规手术' },
  bleeding_severity: { minor: '轻微渗血', active: '活动性出血', floor: '口底血肿' },
  can_compress: { can: '可压迫', cannot: '无法压迫', no_gauze: '无纱布', tried_but_bleeding: '压迫后仍出血' },
  cause_trigger: { has_trigger: '有诱因', no_trigger: '无诱因' },
  rebleed_after_compression: { resolved: '已止血', again: '仍出血' },
  bleeding_location: { lingual: '舌侧', palatal: '腭侧' },
};

const RISK_COLORS: Record<string, string> = {
  none: '#4CAF50',
  low: '#8BC34A',
  medium: '#FFC107',
  high: '#F44336',
};

const RISK_LABELS: Record<string, string> = {
  none: '🟢 无风险',
  low: '🟢 低风险',
  medium: '🟡 中风险',
  high: '🔴 高风险',
};

const isMouthAgent = computed(() => selectedAgent.value === 'mouth' || selectedAgent.value === 'mouth_v2');

const hasSlots = computed(() => Object.keys(collectedSlots.value).length > 0);

const slotProgressPercent = computed(() => {
  const filled = SLOT_NAMES.filter((s) => collectedSlots.value[s]).length;
  return (filled / SLOT_NAMES.length) * 100;
});

const filledSlotCount = computed(() => SLOT_NAMES.filter((s) => collectedSlots.value[s]).length);

const formatSlotName = (key: string): string => {
  return SLOT_DISPLAY_NAMES[key] || key;
};

const formatSlotValue = (key: string, value: string): string => {
  return SLOT_VALUE_DISPLAY[key]?.[value] || value;
};

// 更新槽位状态的函数
const updateSlotState = (slotUpdate: SlotUpdate | null, result: TriageResult | null) => {
  if (slotUpdate) {
    collectedSlots.value = { ...collectedSlots.value, ...slotUpdate };
  }
  if (result) {
    triageResult.value = result;
    // 同时更新已收集的槽位
    if (result.slots) {
      collectedSlots.value = { ...collectedSlots.value, ...result.slots };
    }
  }
};

// 重置槽位状态（切换 Agent 或重新评估时）
const resetSlotState = () => {
  collectedSlots.value = {};
  triageResult.value = null;
};

const nowTs = () => new Date().toLocaleTimeString("zh-CN", { hour12: false });

const pushMessage = (
  role: "user" | "assistant",
  text: string,
  agent?: AgentKey,
  options?: ChatOption[],
  optionsConfig?: OptionsConfig,
  debugInfo?: Record<string, unknown>,
  videoUrl?: string,
  videoPassword?: string,
) => {
  const hasOptions = options && options.length > 0;
  const isMultiSelect = hasOptions && optionsConfig?.multiSelect;
  messages.value.push({
    id: generateUUID(),
    role,
    text,
    timestamp: nowTs(),
    agent,
    options: hasOptions ? options : undefined,
    optionsConfig: hasOptions ? optionsConfig : undefined,
    selectedOptions: isMultiSelect ? new Set<string>() : undefined,
    debugInfo: debugInfo,
    videoUrl,
    videoPassword,
  });
};

const scrollToBottom = () => {
  nextTick(() => {
    const el = scrollContainer.value;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  });
};

const extractError = (err: unknown): string => {
  if (err && typeof err === "object" && "response" in err) {
    const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
    const detail = axiosErr.response?.data?.detail;
    if (detail) {
      return detail;
    }
    return axiosErr.message || "请求失败，请稍后重试";
  }
  return "请求失败，请稍后重试";
};

const normalizeOptions = (raw: unknown): ChatOption[] => {
  if (!Array.isArray(raw)) {
    return [];
  }
  const normalized: ChatOption[] = [];
  for (const item of raw) {
    if (!item || typeof item !== "object") {
      continue;
    }
    const optionCandidate = item as Record<string, unknown>;
    const keyValue = optionCandidate.key;
    const labelValue = optionCandidate.label;
    if (typeof keyValue !== "string" || typeof labelValue !== "string") {
      continue;
    }
    const key = keyValue.trim();
    const label = labelValue.trim();
    if (!key || !label) {
      continue;
    }
    const imageUrlCandidate =
      typeof optionCandidate.image_url === "string"
        ? optionCandidate.image_url
        : typeof optionCandidate.imageUrl === "string"
          ? optionCandidate.imageUrl
          : null;
    const trimmedImageUrl =
      imageUrlCandidate && imageUrlCandidate.trim().length > 0 ? imageUrlCandidate.trim() : null;
    const option: ChatOption = {
      key,
      label,
      imageUrl: trimmedImageUrl,
    };
    normalized.push(option);
  }
  return normalized;
};

const normalizeOptionsConfig = (raw: unknown): OptionsConfig | undefined => {
  if (!raw || typeof raw !== "object") {
    return undefined;
  }
  const config = raw as Record<string, unknown>;
  const multiSelect = config.multi_select === true || config.multiSelect === true;
  const maxSelectRaw = config.max_select ?? config.maxSelect;
  const maxSelect = typeof maxSelectRaw === "number" && maxSelectRaw > 0 ? maxSelectRaw : null;
  const confirmButtonTextRaw = config.confirm_button_text ?? config.confirmButtonText;
  const confirmButtonText =
    typeof confirmButtonTextRaw === "string" && confirmButtonTextRaw.trim()
      ? confirmButtonTextRaw.trim()
      : "确认选择";

  return {
    multiSelect,
    maxSelect,
    confirmButtonText,
  };
};

const OTHER_KEYWORDS = ["其他", "其它", "其他表现", "其他选择", "other"];
const normalizeOptionText = (text: string) => text.replace(/[：:]/g, "").trim();

const extractDecisionLogicFromTriage = (triage: any): string | null => {
  // 深度提取 surgery_type 中的 final_judgment
  // 路径: triage_result -> slots -> surgery_type -> debug_info -> final_judgment
  try {
    const judgment = triage?.slots?.surgery_type?.debug_info?.final_judgment;
    return typeof judgment === 'string' ? judgment : null;
  } catch (e) {
    return null;
  }
};

const isOtherOption = (option: ChatOption): boolean => {
  const normalizedLabel = normalizeOptionText(option.label);
  const normalizedKey = normalizeOptionText(option.key);
  const candidates = [normalizedLabel, normalizedKey].filter(Boolean).map((value) => value.toLowerCase());
  if (candidates.some((value) => OTHER_KEYWORDS.includes(value))) {
    return true;
  }
  return candidates.some((value) => value.startsWith("其他") || value.startsWith("其它"));
};

const loadPresetQuestions = async (agent: AgentKey) => {
  presetError.value = null;
  isLoadingPresets.value = true;

  if (currentPresetRequest.value) {
    currentPresetRequest.value.abort();
  }

  const controller = new AbortController();
  currentPresetRequest.value = controller;

  try {
    const { data } = await request.get(`/api/presets/${agent}`, { signal: controller.signal });
    const questions = Array.isArray(data?.questions) ? data.questions : [];
    presetQuestions.value = questions.filter(
      (item: unknown): item is string => typeof item === "string" && item.trim().length > 0,
    );
  } catch (err) {
    const axiosErr = err as { code?: string };
    if (axiosErr.code !== "ERR_CANCELED") {
      presetError.value = "无法加载预设问题，请稍后重试。";
      presetQuestions.value = [];
    }
  } finally {
    if (currentPresetRequest.value === controller) {
      currentPresetRequest.value = null;
    }
    isLoadingPresets.value = false;
  }
};

const handlePresetClick = (question: string) => {
  if (!question || isLoading.value) {
    return;
  }
  chatInputRef.value?.submitPreset(question);
};

watch(
  () => messages.value.length,
  () => scrollToBottom(),
);

watch(isLoading, (loading) => {
  if (loading) {
    scrollToBottom();
  }
});

watch(error, (val) => {
  if (val) {
    scrollToBottom();
  }
});

const handleReassess = async () => {
  if (isLoading.value || (selectedAgent.value !== "mouth" && selectedAgent.value !== "mouth_v2")) {
    return;
  }
  const lastPrompt = lastMouthUserMessage.value?.text.trim();
  const baseMessage =
    lastPrompt && lastPrompt.length > 0 ? lastPrompt : DEFAULT_MOUTH_REASSESS_PROMPT;
  error.value = null;
  
  // 生成新 thread_id
  generateNewThreadId();
  
  // 重置槽位状态
  resetSlotState();

  const controller = new AbortController();
  currentRequest.value = controller;
  isLoading.value = true;

  const reassessBody = {
    message: baseMessage,
    agent: selectedAgent.value,
    reset_state: true,
    debug_mode: debugEnabled.value,
    thread_id: threadId.value,
  };
  console.log(
    "[重新评估] 请求体 (debug_mode=%s debugEnabled=%s): %s",
    reassessBody.debug_mode,
    debugEnabled.value,
    JSON.stringify(reassessBody, null, 2),
  );

  try {
    const { data } = await request.post(
      "/api/chat/reassess",
      reassessBody,
      { signal: controller.signal },
    );

    const reply = typeof data?.reply === "string" ? data.reply.trim() : "";
    const agent = (data?.agent as AgentKey | undefined) ?? selectedAgent.value;
    const options = normalizeOptions(data?.options);
    const optionsConfig = normalizeOptionsConfig(data?.options_config);
    
    // 更新槽位状态
    if (isMouthAgent.value && debugEnabled.value) {
      updateSlotState(data?.slot_update, data?.triage_result);
    }
    
    // 合并 Triage 中的 Decision Logic 到 debugInfo 以便展示
    let debugInfo = data?.debug_info || {};
    const triageJudgment = extractDecisionLogicFromTriage(data?.triage_result);
    if (triageJudgment) {
      debugInfo = { ...debugInfo, decision_logic: triageJudgment };
    }

    pushMessage("assistant", reply || "(Agent 未返回内容)", agent, options, optionsConfig, debugInfo, data?.video_url, data?.video_password);
    hasReassessed.value = true;
  } catch (err) {
    const axiosErr = err as { code?: string };
    if (axiosErr.code === "ERR_CANCELED") {
      pushMessage("assistant", "对话已被中断。", selectedAgent.value);
    } else {
      const message = extractError(err);
      error.value = message;
    }
  } finally {
    isLoading.value = false;
    currentRequest.value = null;
  }
};

const attemptAutoReassess = () => {
  if (!pendingAutoReassess.value || (selectedAgent.value !== "mouth" && selectedAgent.value !== "mouth_v2") || isLoading.value) {
    return;
  }
  pendingAutoReassess.value = false;
  void handleReassess();
};

watch(
  selectedAgent,
  (agent) => {
    loadPresetQuestions(agent);
    // 重置槽位状态
    resetSlotState();
    if (agent === "mouth" || agent === "mouth_v2") {
      // 切换到口腔 Agent 时生成新 thread_id
      generateNewThreadId();
      pendingAutoReassess.value = true;
      attemptAutoReassess();
    } else {
      pendingAutoReassess.value = false;
    }
  },
  { immediate: true },
);

const executePrompt = async (
  input: string,
  { skipUserPush = false }: { skipUserPush?: boolean } = {},
) => {
  const trimmedInput = input.trim();
  if (!trimmedInput) {
    return;
  }
  error.value = null;
  hasReassessed.value = false;

  if (!skipUserPush) {
    pushMessage("user", trimmedInput, selectedAgent.value);
    scrollToBottom();
  }

  const controller = new AbortController();
  currentRequest.value = controller;
  isLoading.value = true;

  try {
    const chatBody = { message: trimmedInput, agent: selectedAgent.value, debug_mode: debugEnabled.value, thread_id: threadId.value };
    console.log(
      "[对话] 请求体 (debug_mode=%s debugEnabled=%s): %s",
      chatBody.debug_mode,
      debugEnabled.value,
      JSON.stringify(chatBody, null, 2),
    );
    const { data } = await request.post("/api/chat", chatBody, { signal: controller.signal });

    const reply = typeof data?.reply === "string" ? data.reply.trim() : "";
    const agent = (data?.agent as AgentKey | undefined) ?? selectedAgent.value;
    const options = normalizeOptions(data?.options);
    const optionsConfig = normalizeOptionsConfig(data?.options_config);
    
    // 更新槽位状态
    if (isMouthAgent.value && debugEnabled.value) {
      updateSlotState(data?.slot_update, data?.triage_result);
    }
    
    // 合并 Triage 中的 Decision Logic 到 debugInfo 以便展示
    let debugInfo = data?.debug_info || {};
    const triageJudgment = extractDecisionLogicFromTriage(data?.triage_result);
    if (triageJudgment) {
      debugInfo = { ...debugInfo, decision_logic: triageJudgment };
    }

    pushMessage("assistant", reply || "(Agent 未返回内容)", agent, options, optionsConfig, debugInfo, data?.video_url, data?.video_password);
  } catch (err) {
    const axiosErr = err as { code?: string };
    if (axiosErr.code === "ERR_CANCELED") {
      pushMessage("assistant", "对话已被中断。", selectedAgent.value);
    } else {
      const message = extractError(err);
      error.value = message;
    }
  } finally {
    isLoading.value = false;
    currentRequest.value = null;
  }
};

const handleSubmit = async (input: string) => {
  if (!input || input.trim().length === 0) {
    return;
  }
  await executePrompt(input);
};

// Debug info helper function
const getDebugFinalJudgment = (msg: ChatMessage): string | null => {
  if (!msg.debugInfo) return null;
  const debugInfo = msg.debugInfo as Record<string, any>;

  // Case 1: 术式解析结果 (type === 'surgery_type_parse')
  if (debugInfo.type === "surgery_type_parse" && debugInfo.data) {
    const data = debugInfo.data;
    if (data.final_judgment) {
      return String(data.final_judgment);
    }
  }

  // Case 2: 槽位汇总 (slots_collected === true)
  if (debugInfo.slots_collected && debugInfo.slots && typeof debugInfo.slots === "object") {
    // 遍历 slots 查找包含 debug_info 的对象
    for (const key in debugInfo.slots) {
      if (key.endsWith("_debug_info")) {
        const slotDebug = debugInfo.slots[key];
        if (slotDebug && typeof slotDebug === "object" && slotDebug.final_judgment) {
          return String(slotDebug.final_judgment);
        }
      }
    }
  }

  // Case 3: 通用决策逻辑 (generic decision_logic)
  if (debugInfo.decision_logic) {
    return String(debugInfo.decision_logic);
  }

  return null;
};

// Multi-select helper functions

const isOptionSelected = (msg: ChatMessage, optionKey: string): boolean => {
  return msg.selectedOptions?.has(optionKey) ?? false;
};

const isOptionDisabled = (msg: ChatMessage, optionKey: string): boolean => {
  if (!msg.optionsConfig?.multiSelect) {
    return false;
  }
  const maxSelect = msg.optionsConfig.maxSelect;
  if (!maxSelect) {
    return false;
  }
  const currentSize = msg.selectedOptions?.size ?? 0;
  // Disable if max reached and this option is not already selected
  return currentSize >= maxSelect && !isOptionSelected(msg, optionKey);
};

const toggleOptionSelection = (msg: ChatMessage, optionKey: string): void => {
  if (!msg.selectedOptions) {
    msg.selectedOptions = new Set<string>();
  }
  if (msg.selectedOptions.has(optionKey)) {
    msg.selectedOptions.delete(optionKey);
  } else {
    const maxSelect = msg.optionsConfig?.maxSelect;
    if (!maxSelect || msg.selectedOptions.size < maxSelect) {
      msg.selectedOptions.add(optionKey);
    }
  }
  // Trigger reactivity update
  const index = messages.value.findIndex((m) => m.id === msg.id);
  if (index !== -1) {
    messages.value[index] = { ...msg, selectedOptions: new Set(msg.selectedOptions) };
  }
};

const handleOptionClick = async (msg: ChatMessage, option: ChatOption): Promise<void> => {
  if (isLoading.value) {
    return;
  }
  if (msg.agent && msg.agent !== selectedAgent.value) {
    return;
  }

  // If multi-select mode, toggle selection instead of submitting
  if (msg.optionsConfig?.multiSelect) {
    if (!isOptionDisabled(msg, option.key)) {
      toggleOptionSelection(msg, option.key);
    }
    return;
  }

  // Single-select mode: use existing handleOptionSelect logic
  await handleOptionSelect(msg.id, option);
};

const handleMultiSelectConfirm = async (msg: ChatMessage): Promise<void> => {
  if (isLoading.value || !msg.selectedOptions?.size) {
    return;
  }
  if (msg.agent && msg.agent !== selectedAgent.value) {
    return;
  }

  // Get selected option keys and format as "B,C,D"
  const selectedKeys = Array.from(msg.selectedOptions).sort();
  const selectionText = selectedKeys.join(",");

  // Also get labels for user display
  const selectedLabels = selectedKeys
    .map((key) => msg.options?.find((opt) => opt.key === key)?.label)
    .filter(Boolean)
    .join("、");

  // Push user message with formatted selection
  pushMessage("user", `选择: ${selectedLabels}`, selectedAgent.value);
  scrollToBottom();

  // Clear options from the message
  const targetIndex = messages.value.findIndex((m) => m.id === msg.id);
  if (targetIndex !== -1) {
    const current = messages.value[targetIndex];
    messages.value[targetIndex] = { ...current, options: undefined, selectedOptions: undefined };
  }

  // Send selection to agent with format "B,C,D"
  await executePrompt(selectionText, { skipUserPush: true });
};

const handleOptionSelect = async (messageId: string, option: ChatOption) => {
  if (isLoading.value) {
    return;
  }
  const normalizedLabel = option.label.trim() || option.key.trim();
  if (!normalizedLabel) {
    return;
  }
  const targetIndex = messages.value.findIndex((msg) => msg.id === messageId);
  if (targetIndex !== -1) {
    const targetMessage = messages.value[targetIndex];
    if (targetMessage.agent && targetMessage.agent !== selectedAgent.value) {
      return;
    }
  }

  // 检测是否为"其他"、"其他表现"或"其他选择"选项
  if (isOtherOption(option)) {
    const cleanedLabel = normalizeOptionText(normalizedLabel) || normalizedLabel;
    // 显示输入框对话框
    pendingOtherOption.value = { messageId, option: { ...option, label: cleanedLabel } };
    otherInputText.value = "";
    showOtherInputDialog.value = true;
    return;
  }

  pushMessage("user", normalizedLabel, selectedAgent.value);
  scrollToBottom();

  if (targetIndex !== -1) {
    const current = messages.value[targetIndex];
    messages.value[targetIndex] = { ...current, options: undefined };
  }

  await executePrompt(normalizedLabel, { skipUserPush: true });
};

const handleOtherInputSubmit = async (userInput: string) => {
  if (!pendingOtherOption.value || !userInput || !userInput.trim()) {
    showOtherInputDialog.value = false;
    pendingOtherOption.value = null;
    return;
  }

  const { messageId } = pendingOtherOption.value;
  const trimmedInput = userInput.trim();

  // 关闭对话框
  showOtherInputDialog.value = false;
  pendingOtherOption.value = null;

  // 推送用户的描述作为消息
  pushMessage("user", trimmedInput, selectedAgent.value);
  scrollToBottom();

  // 移除选项
  const targetIndex = messages.value.findIndex((msg) => msg.id === messageId);
  if (targetIndex !== -1) {
    const current = messages.value[targetIndex];
    messages.value[targetIndex] = { ...current, options: undefined };
  }

  // 发送用户输入给agent
  await executePrompt(trimmedInput, { skipUserPush: true });
};

const handleOtherInputCancel = () => {
  showOtherInputDialog.value = false;
  pendingOtherOption.value = null;
  otherInputText.value = "";
};

const handleAbort = () => {
  const controller = currentRequest.value;
  if (controller) {
    controller.abort();
  }
};

const toggleDebug = () => {
  debugEnabled.value = !debugEnabled.value;
  console.log("[Debug 切换] debugEnabled:", debugEnabled.value);
};

const handleLogout = () => {
  removeToken();
  router.push("/login");
};

onMounted(() => {
  scrollToBottom();
});

onBeforeUnmount(() => {
  currentPresetRequest.value?.abort();
});

watch(isLoading, (loading) => {
  if (!loading) {
    attemptAutoReassess();
  }
});

watch(showOtherInputDialog, (show) => {
  if (show) {
    nextTick(() => {
      otherInputTextarea.value?.focus();
    });
  }
});
</script>

<style scoped>
.loading-dots {
  display: inline-flex;
  align-items: center;
  margin-left: 0.25rem;
}

.loading-dots span {
  width: 0.35rem;
  height: 0.35rem;
  margin-left: 0.2rem;
  border-radius: 9999px;
  background-color: #38bdf8;
  opacity: 0.4;
  animation: dotPulse 1s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dotPulse {
  0%,
  100% {
    opacity: 0.2;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-0.2rem);
  }
}
</style>
