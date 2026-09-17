<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-900 px-4">
    <div class="w-full max-w-md">
      <div class="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-xl backdrop-blur">
        <div class="mb-8 text-center">
          <img alt="Logo" src="../assets/logo.svg" class="mx-auto h-16 w-16" />
          <h1 class="mt-4 text-2xl font-bold text-white">AI Agent 对话</h1>
          <p class="mt-2 text-sm text-slate-400">请登录以继续</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-6">
          <div>
            <label for="username" class="block text-sm font-medium text-slate-300">
              用户名
            </label>
            <input
              id="username"
              v-model="username"
              type="text"
              required
              :disabled="isLoading"
              class="mt-2 block w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:opacity-60"
              placeholder="请输入用户名"
            />
          </div>

          <div>
            <label for="password" class="block text-sm font-medium text-slate-300">
              密码
            </label>
            <div class="relative mt-2">
              <input
                id="password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                required
                :disabled="isLoading"
                class="block w-full rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 pr-12 text-slate-100 placeholder-slate-500 focus:border-sky-400 focus:outline-none focus:ring-2 focus:ring-sky-400/40 disabled:opacity-60"
                placeholder="请输入密码"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 transition"
                :disabled="isLoading"
              >
                <!-- 睁眼图标 (密码可见) -->
                <svg v-if="showPassword" class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <!-- 闭眼图标 (密码隐藏) -->
                <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              </button>
            </div>
          </div>

          <div v-if="error" class="rounded-lg bg-rose-950/50 border border-rose-500/30 px-4 py-3 text-sm text-rose-300">
            {{ error }}
          </div>

          <button
            type="submit"
            :disabled="isLoading || !username || !password"
            class="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span v-if="isLoading" class="flex items-center justify-center gap-2">
              <svg class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-opacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
              </svg>
              登录中...
            </span>
            <span v-else>登录</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import { setToken } from "../utils/auth";

const router = useRouter();

const username = ref("");
const password = ref("");
const showPassword = ref(false);
const isLoading = ref(false);
const error = ref<string | null>(null);

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

const handleLogin = async () => {
  if (!username.value || !password.value) {
    return;
  }

  isLoading.value = true;
  error.value = null;

  try {
    const endpoint = apiBaseUrl ? `${apiBaseUrl}/api/auth/login` : "/api/auth/login";
    const response = await axios.post(endpoint, {
      username: username.value,
      password: password.value,
    });

    const { access_token } = response.data;
    setToken(access_token);
    router.push("/");
  } catch (err) {
    if (axios.isAxiosError(err)) {
      const detail = err.response?.data?.detail;
      error.value = detail || "登录失败，请检查用户名和密码";
    } else {
      error.value = "登录失败，请稍后重试";
    }
  } finally {
    isLoading.value = false;
  }
};
</script>
