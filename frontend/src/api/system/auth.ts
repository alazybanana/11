/**
 * system 模块 —— 认证接口（登录 / 注册 / 登出 / 当前用户 / 改密）。
 */

import { get, post } from '@/utils/request'

import type {
  ChangePasswordPayload,
  LoginPayload,
  LoginUser,
  RegisterPayload,
  RoleOption,
  TokenData,
  User,
} from './types'

/** 登录：校验账号密码并签发访问令牌 */
export function login(payload: LoginPayload): Promise<TokenData> {
  return post<TokenData>('/system/auth/login', payload)
}

/** 公开注册：自选身份，注册后即可登录（仅游客权限），人事主管批准后所选角色生效 */
export function register(payload: RegisterPayload): Promise<User> {
  return post<User>('/system/auth/register', payload)
}

/** 注册页可选身份列表（公开接口，无需登录） */
export function listRegisterRoles(): Promise<RoleOption[]> {
  return get<RoleOption[]>('/system/auth/roles-available')
}

/** 登出：令牌为无状态实现，服务端只记录日志，前端自行丢弃令牌 */
export function logout(): Promise<void> {
  return post<void>('/system/auth/logout')
}

/** 当前登录用户信息（含角色与权限编码） */
export function getCurrentUser(): Promise<LoginUser> {
  return get<LoginUser>('/system/auth/me')
}

/** 修改自己的密码 */
export function changePassword(payload: ChangePasswordPayload): Promise<void> {
  return post<void>('/system/auth/change-password', payload)
}
