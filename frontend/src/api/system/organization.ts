/**
 * system 模块 —— 组织与人员信息管理接口。
 */

import type { PageData } from '@/types/api'
import { del, get, post, put } from '@/utils/request'

import type {
  Employee,
  EmployeePayload,
  EmployeeQuery,
  Organization,
  OrganizationPayload,
  OrganizationQuery,
  OrganizationTree,
} from './types'

// --------------------------------------------------------------------------- #
// 组织（树形结构）
// --------------------------------------------------------------------------- #
/** 组织结构树（一次取回整棵树） */
export function getOrganizationTree(keyword?: string): Promise<OrganizationTree[]> {
  return get<OrganizationTree[]>('/system/organizations/tree', { keyword })
}

export function listOrganizations(query: OrganizationQuery): Promise<PageData<Organization>> {
  return get<PageData<Organization>>('/system/organizations', query)
}

export function getOrganization(id: number): Promise<Organization> {
  return get<Organization>(`/system/organizations/${id}`)
}

export function createOrganization(payload: OrganizationPayload): Promise<Organization> {
  return post<Organization>('/system/organizations', payload)
}

export function updateOrganization(
  id: number,
  payload: Partial<OrganizationPayload>,
): Promise<Organization> {
  return put<Organization>(`/system/organizations/${id}`, payload)
}

export function deleteOrganization(id: number): Promise<void> {
  return del<void>(`/system/organizations/${id}`)
}

// --------------------------------------------------------------------------- #
// 人员档案
// --------------------------------------------------------------------------- #
export function listEmployees(query: EmployeeQuery): Promise<PageData<Employee>> {
  return get<PageData<Employee>>('/system/employees', query)
}

export function getEmployee(id: number): Promise<Employee> {
  return get<Employee>(`/system/employees/${id}`)
}

export function createEmployee(payload: EmployeePayload): Promise<Employee> {
  return post<Employee>('/system/employees', payload)
}

export function updateEmployee(id: number, payload: Partial<EmployeePayload>): Promise<Employee> {
  return put<Employee>(`/system/employees/${id}`, payload)
}

export function deleteEmployee(id: number): Promise<void> {
  return del<void>(`/system/employees/${id}`)
}
