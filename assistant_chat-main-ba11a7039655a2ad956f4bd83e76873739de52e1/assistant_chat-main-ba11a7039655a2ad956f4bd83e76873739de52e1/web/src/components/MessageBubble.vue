<template>
  <div
    :class="[
      'max-w-3xl mx-auto px-4 py-3 flex gap-3',
      role === 'assistant' ? 'flex-row' : 'flex-row-reverse',
    ]"
  >
    <div class="shrink-0">
      <div
        v-if="avatarSrc"
        class="w-10 h-10 rounded-full overflow-hidden border border-slate-700/70 bg-slate-800"
      >
        <img
          :src="avatarSrc"
          :alt="avatarAlt || (role === 'assistant' ? 'AI Avatar' : 'User Avatar')"
          class="h-full w-full object-cover"
        />
      </div>
      <div
        v-else
        :class="[
          'w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold uppercase select-none',
          role === 'assistant' ? 'bg-slate-700 text-sky-300' : 'bg-sky-500 text-white',
        ]"
      >
        {{ role === 'assistant' ? 'AI' : '我' }}
      </div>
    </div>
    <div
      :class="[
        'flex flex-1',
        role === 'assistant' ? 'justify-start' : 'justify-end',
      ]"
    >
      <div
        :class="[
          'flex items-end gap-2 max-w-full',
          role === 'assistant' ? 'flex-row' : 'flex-row-reverse',
        ]"
      >
        <div
          :class="[
            'inline-flex items-center max-w-[75vw] rounded-2xl px-4 py-1.5 text-base leading-tight whitespace-pre-wrap break-words shadow-sm text-left',
            role === 'assistant' ? 'bg-agent-assistant/80 text-slate-100' : 'bg-agent-user text-white',
          ]"
        >
          <slot />
        </div>
        <span class="text-xs text-slate-500 whitespace-nowrap">
          {{ timestamp }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  role: "assistant" | "user";
  timestamp: string;
  avatarSrc?: string | null;
  avatarAlt?: string;
}>();
</script>
