import { createRouter, createWebHistory } from 'vue-router'
import type { Router } from 'vue-router'

import { constantRoutes } from './routes'

const router: Router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: constantRoutes,
})

// 浏览器标题跟随路由 meta.title
router.afterEach((to) => {
  const appTitle = import.meta.env.VITE_APP_TITLE || 'BH-ERP'
  document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
})

/**
 * 登录路由守卫：以 localStorage 中是否存在登录结果（`bh-erp-user`）判定登录态。
 *
 * - 未登录访问业务页 → 重定向 `/login` 并携带 redirect；
 * - 已登录访问 `/login` → 回工作台。
 *
 * 后端登录为简化版（无 JWT），登录成功后由登录页把返回结果写入 `bh-erp-user`，
 * 退出登录（头部「退出」按钮）清除该键即可。
 */
const LOGIN_PATH = '/login'

function isLoggedIn(): boolean {
  return Boolean(localStorage.getItem('bh-erp-user'))
}

router.beforeEach((to) => {
  if (to.path === LOGIN_PATH) {
    return isLoggedIn() ? { path: '/dashboard' } : undefined
  }
  return isLoggedIn() ? undefined : { path: LOGIN_PATH, query: { redirect: to.fullPath } }
})

export default router
