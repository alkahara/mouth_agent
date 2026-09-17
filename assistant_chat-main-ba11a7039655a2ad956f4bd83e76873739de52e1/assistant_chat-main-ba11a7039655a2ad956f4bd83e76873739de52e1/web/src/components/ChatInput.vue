<template>
  <form @submit.prevent="emitSubmit" class="w-full">
    <div class="max-w-3xl mx-auto px-4 py-4">
      <div class="relative">
        <div class="flex items-center gap-3">
          <textarea
            v-model="draft"
            :disabled="isSending"
            placeholder="输入你的问题，按 Enter 发送"
            class="flex-1 resize-none rounded-xl bg-slate-900 border border-slate-700/70 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/40 px-4 py-3 text-base leading-relaxed text-slate-100 placeholder-slate-500"
            rows="3"
            @keydown.enter.exact.prevent="emitSubmit"
          ></textarea>
          <button
            type="button"
            class="inline-flex h-12 min-w-[98px] items-center justify-center gap-2 rounded-lg px-5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
            :class="isSending ? 'bg-rose-500 hover:bg-rose-400 text-white focus-visible:outline-rose-300' : 'bg-sky-500 hover:bg-sky-400 text-white focus-visible:outline-sky-300 disabled:bg-slate-600'"
            :disabled="!isSending && draft.trim().length === 0"
            @click="handlePrimaryClick"
          >
            <template v-if="isSending">
              <span>中断</span>
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="1.5"></rect>
              </svg>
            </template>
            <template v-else>
              <span>发送</span>
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" aria-hidden="true">
                <path stroke-linecap="round" stroke-linejoin="round" d="m4.5 19.5 15-7.5-15-7.5 3.75 7.5L4.5 19.5z" />
              </svg>
            </template>
          </button>
          <button
            v-if="showReassess"
            type="button"
            class="inline-flex h-12 min-w-[98px] items-center justify-center gap-2 rounded-lg bg-amber-500 px-5 text-sm font-medium text-slate-900 transition hover:bg-amber-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-300"
            :disabled="isSending || !canReassess"
            @click="emitReassess"
          >
            <span>重新评估</span>
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
              <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5a7.5 7.5 0 0113.134-4.88M4.5 13.5a7.5 7.5 0 0013.134 4.88M4.5 10.5H9m-4.5 0V6m15 7.5H15m4.5 0V18" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{
  isSending: boolean;
  showReassess: boolean;
  canReassess: boolean;
}>();

const emit = defineEmits<{
  (e: "submit", value: string): void;
  (e: "abort"): void;
  (e: "reassess"): void;
}>();

const draft = ref("");

const emitSubmit = () => {
  const value = draft.value.trim();
  if (!value || props.isSending) {
    return;
  }
  emit("submit", value);
  draft.value = "";
};

const handlePrimaryClick = () => {
  if (props.isSending) {
    emit("abort");
    return;
  }
  emitSubmit();
};

const emitReassess = () => {
  if (props.isSending || !props.canReassess) {
    return;
  }
  emit("reassess");
};

const submitPreset = (value: string) => {
  if (props.isSending) {
    return;
  }
  draft.value = value;
  emitSubmit();
};

defineExpose({ submitPreset });
</script>
