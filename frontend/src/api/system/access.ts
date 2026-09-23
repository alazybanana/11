/**
 * system 模块 —— 系统访问权限管理接口：账号、角色（访问范围）、权限资源。
 */

import type { PageData } from '@/types/api'
import { del, get, post, put } from '@/utils/request'

import type {
  Permission,
  PermissionPayload,
  PermissionQuery,
  PermissionTree,
  Role,
  RolePayload,
  RoleQuery,
  User,
  UserPayload,
  UserQuery,
  UserUpdatePayload,
} from './types'

// --------------------------------------------------------------------------- #
// 账号
// --------------------------------------------------------------------------- #
export function listUsers(query: UserQuery): Promise<PageData<User>> {
  return get<PageData<User>>('/system/users', query)
}

export function getUser(id: number): Promise<User> {
  return get<User>(`/system/users/${id}`)
}

export function createUser(payload: UserPayload): Promise<User> {
  return post<User>('/system/users', payload)
}

export function updateUser(id: number, payload: UserUpdatePayload): Promise<User> {
  return put<User>(`/system/users/${id}`, payload)
}

export function deleteUser(id: number): Promise<void> {
  return del<void>(`/system/users/${id}`)
}

/** 分配账号角色（传空数组表示清空） */
export function assignUserRoles(id: number, roleIds: number[]): Promise<User> {
  return put<User>(`/system/users/${id}/roles`, { role_ids: roleIds })
}

/** 批准注册账号（仅人事主管 / 超管可用），所选角色权限自此生效 */
export function approveUser(id: number): Promise<User> {
  return post<User>(`/system/users/${id}/approve`)
}

/** 驳回注册账号（仅人事主管 / 超管可用），该账号无法再登录 */
export function rejectUser(id: number): Promise<User> {
  return post<User>(`/system/users/${id}/reject`)
}

/** 管理员重置账号密码 */
export function resetUserPassword(id: number, password: string): Promise<void> {
  return put<void>(`/system/users/${id}/password`, { password })
}

// --------------------------------------------------------------------------- #
// 角色
// --------------------------------------------------------------------------- #
export function listRoles(query: RoleQuery): Promise<PageData<Role>> {
  return get<PageData<Role>>('/system/roles', query)
}

export function getRole(id: number): Promise<Role> {
  return get<Role>(`/system/roles/${id}`)
}

export function createRole(payload: RolePayload): Promise<Role> {
  return post<Role>('/system/roles', payload)
}

export function updateRole(id: number, payload: Partial<RolePayload>): Promise<Role> {
  return put<Role>(`/system/roles/${id}`, payload)
}

export function deleteRole(id: number): Promise<void> {
  return del<void>(`/system/roles/${id}`)
}

/** 分配角色权限 */
export function assignRolePermissions(id: number, permissionIds: number[]): Promise<Role> {
  return put<Role>(`/system/roles/${id}/permissions`, { permission_ids: permissionIds })
}

// --------------------------------------------------------------------------- #
// 权限资源
// --------------------------------------------------------------------------- #
/** 权限资源树（角色授权时用） */
export function getPermissionTree(): Promise<PermissionTree[]> {
  return get<PermissionTree[]>('/system/permissions/tree')
}

export function listPermissions(query: PermissionQuery): Promise<PageData<Permission>> {
  return get<PageData<Permission>>('/system/permissions', query)
}

export function getPermission(id: number): Promise<Permission> {
  return get<Permission>(`/system/permissions/${id}`)
}

export function createPermission(payload: PermissionPayload): Promise<Permission> {
  return post<Permission>('/system/permissions', payload)
}

export function updatePermission(
  id: number,
  payload: Partial<PermissionPayload>,
): Promise<Permission> {
  return put<Permission>(`/system/permissions/${id}`, payload)
}

export function deletePermission(id: number): Promise<void> {
  return del<void>(`/system/permissions/${id}`)
}
