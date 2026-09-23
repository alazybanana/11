import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getCurrentUser, login as loginApi, logout as logoutApi } from '@/api/system'
import type { LoginPayload, LoginUser } from '@/api/system/types'
import { clearAuth, getStoredUser, getToken, setStoredUser, setToken } from '@/utils/token'

/**
 * 登录态（由 system 模块提供）。
 *
 * 令牌存在 localStorage，刷新页面后先读缓存渲染，再由 `loadUser()` 拉最新权限。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(getToken())
  const user = ref<LoginUser | null>(getStoredUser<LoginUser>())

  const isLoggedIn = computed(() => Boolean(token.value))
  const isSuperuser = computed(() => user.value?.is_superuser === true)

  /** 是否拥有某个权限编码（超级管理员恒为 true） */
  function can(permissionCode: string): boolean {
    if (isSuperuser.value) {
      return true
    }
    return user.value?.permissions.includes(permissionCode) ?? false
  }

  async function login(payload: LoginPayload): Promise<LoginUser> {
    const data = await loginApi(payload)
    token.value = data.access_token
    user.value = data.user
    setToken(data.access_token)
    setStoredUser(data.user)
    return data.user
  }

  /** 拉取当前用户最新信息（角色 / 权限可能在别处被改过） */
  async function loadUser(): Promise<LoginUser> {
    const data = await getCurrentUser()
    user.value = data
    setStoredUser(data)
    return data
  }

  function reset(): void {
    token.value = ''
    user.value = null
    clearAuth()
  }

  async function logout(): Promise<void> {
    try {
      await logoutApi()
    } catch {
      // 令牌已过期也要允许退出，忽略服务端错误
    }
    reset()
  }

  return { token, user, isLoggedIn, isSuperuser, can, login, loadUser, logout, reset }
})
