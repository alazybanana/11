import axios from 'axios'
import type { AxiosError, AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

import type { ApiResponse } from '@/types/api'
import { SUCCESS_CODE, UNAUTHORIZED_CODE } from '@/types/api'
import { clearAuth, getToken } from '@/utils/token'

/**
 * 全局 axios 实例。
 *
 * - baseURL 取 `VITE_API_BASE_URL`（默认 `/api/v1`）
 * - 开发环境由 `vite.config.ts` 的 proxy 转发到后端 http://127.0.0.1:8000
 * - 下方 `get/post/put/del` 会自动拆包统一响应 `{ code, message, data }`，
 *   业务代码直接拿到 `data`；`code !== 0` 时抛出 `Error(message)`
 */
const request: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** 把后端错误响应或网络错误统一转换成可读的错误信息 */
function toErrorMessage(error: AxiosError<ApiResponse<unknown>>): string {
  const body = error.response?.data

  if (
    body !== null &&
    body !== undefined &&
    typeof body === 'object' &&
    typeof body.message === 'string' &&
    body.message
  ) {
    return body.message
  }

  return error.response ? `请求失败（HTTP ${error.response.status}）` : error.message
}

/** 自动附带登录令牌：`Authorization: Bearer <token>` */
request.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(undefined, (error: AxiosError<ApiResponse<unknown>>) =>
  Promise.reject(new Error(toErrorMessage(error))),
)

/** 拆包统一响应结构，返回业务数据 */
async function unwrap<T>(promise: Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  const response = await promise
  const body = response.data

  // 兼容未按统一规范返回的响应
  if (body === null || typeof body !== 'object' || !('code' in body)) {
    return body as unknown as T
  }

  if (body.code !== SUCCESS_CODE) {
    // 登录态已失效：清掉本地令牌并回到登录页（用 location 避免与 router 循环依赖）
    if (body.code === UNAUTHORIZED_CODE) {
      clearAuth()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    throw new Error(body.message || '请求失败')
  }

  return body.data
}

/**
 * GET 请求。`params` 用 `object` 而非 `Record<string, unknown>`：
 * TypeScript 的 interface 没有隐式索引签名，写 `Record<string, unknown>`
 * 会导致各模块自己的查询参数 interface（如 `MaterialQuery`）传不进来。
 */
export function get<T>(url: string, params?: object): Promise<T> {
  return unwrap<T>(request.get(url, { params }))
}

export function post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return unwrap<T>(request.post(url, data, config))
}

export function put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return unwrap<T>(request.put(url, data, config))
}

export function del<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
  return unwrap<T>(request.delete(url, config))
}

export default request
