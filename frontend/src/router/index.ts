import { createRouter, createWebHistory } from 'vue-router'
import type { Router } from 'vue-router'

import { pinia } from '@/stores'
import { useAuthStore } from '@/stores/modules/auth'

import { constantRoutes } from './routes'

const router: Router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: constantRoutes,
})

/**
 * 登录态校验（由 system 模块提供）。
 *
 * - 未登录访问业务页面 → 跳登录页，并记住原地址
 * - 已登录访问登录页 → 直接进工作台
 * - 只有令牌没有用户信息（例如手工改了 localStorage）→ 拉一次用户信息
 */
router.beforeEach(async (to) => {
  const auth = useAuthStore(pinia)

  if (to.path === '/login') {
    return auth.isLoggedIn ? { path: '/dashboard' } : true
  }

  if (!auth.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!auth.user) {
    try {
      await auth.loadUser()
    } catch {
      auth.reset()
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  return true
})

// 浏览器标题跟随路由 meta.title
router.afterEach((to) => {
  const appTitle = import.meta.env.VITE_APP_TITLE || 'BH-ERP'
  document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
})

export default router
