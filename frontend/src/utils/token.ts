/**
 * 登录令牌与登录用户信息的本地存储。
 *
 * 单独抽出来是为了避免循环依赖：
 * `utils/request.ts` 需要读令牌，但它不能 import store / router。
 */

const TOKEN_KEY = 'bh-erp-token'
const USER_KEY = 'bh-erp-user'

/** 读取访问令牌，未登录返回空串 */
export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

/** 读取本地缓存的登录用户信息（用于刷新页面后立即渲染） */
export function getStoredUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setStoredUser(user: unknown): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

/** 清除登录态（令牌 + 用户信息） */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
