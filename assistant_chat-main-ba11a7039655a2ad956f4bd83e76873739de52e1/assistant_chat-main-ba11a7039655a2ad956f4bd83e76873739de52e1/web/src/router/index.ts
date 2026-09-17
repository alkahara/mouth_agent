/**
 * Vue Router configuration
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router";
import { isAuthenticated } from "../utils/auth";

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("../views/Login.vue"),
    meta: { requiresAuth: false },
  },
  {
    path: "/",
    name: "Chat",
    component: () => import("../views/Chat.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Navigation guard
router.beforeEach((to, _from, next) => {
  const requiresAuth = to.meta.requiresAuth !== false;

  if (requiresAuth && !isAuthenticated()) {
    next("/login");
  } else if (to.path === "/login" && isAuthenticated()) {
    next("/");
  } else {
    next();
  }
});

export default router;
