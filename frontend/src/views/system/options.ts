/**
 * system 模块的枚举 → 展示文案映射。
 *
 * 与后端 `app/modules/system/enums.py` 一一对应，
 * 页面统一从这里取下拉选项与表格展示文案，避免各处硬编码中文字符串。
 */

import type {
  BomStatus,
  CommonStatus,
  DataScope,
  EmployeeStatus,
  Gender,
  LogStatus,
  MaterialType,
  OperationAction,
  OrgType,
  PermissionType,
  RoutingStatus,
  SourceType,
} from '@/api/system/types'

/** 下拉选项 */
export interface Option<T extends string> {
  label: string
  value: T
}

/** el-tag 支持的语义色 */
export type TagType = 'success' | 'info' | 'warning' | 'danger' | 'primary'

function toOptions<T extends string>(labels: Record<T, string>): Option<T>[] {
  return (Object.keys(labels) as T[]).map((value) => ({ label: labels[value], value }))
}

// --------------------------------------------------------------------------- #
// 通用状态
// --------------------------------------------------------------------------- #
export const COMMON_STATUS_LABELS: Record<CommonStatus, string> = {
  ENABLED: '启用',
  DISABLED: '停用',
}
export const COMMON_STATUS_TAGS: Record<CommonStatus, TagType> = {
  ENABLED: 'success',
  DISABLED: 'info',
}
export const COMMON_STATUS_OPTIONS = toOptions(COMMON_STATUS_LABELS)

// --------------------------------------------------------------------------- #
// 物料 / 产品
// --------------------------------------------------------------------------- #
export const MATERIAL_TYPE_LABELS: Record<MaterialType, string> = {
  RAW: '原材料',
  SEMI: '半成品',
  FINISHED: '成品',
  PACK: '包装物',
}
export const MATERIAL_TYPE_OPTIONS = toOptions(MATERIAL_TYPE_LABELS)

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  PURCHASE: '采购',
  MAKE: '自制',
}
export const SOURCE_TYPE_TAGS: Record<SourceType, TagType> = {
  PURCHASE: 'warning',
  MAKE: 'success',
}
export const SOURCE_TYPE_OPTIONS = toOptions(SOURCE_TYPE_LABELS)

// --------------------------------------------------------------------------- #
// BOM / 工艺路线状态
// --------------------------------------------------------------------------- #
export const BOM_STATUS_LABELS: Record<BomStatus, string> = {
  DRAFT: '草稿',
  RELEASED: '已发布',
  OBSOLETE: '已作废',
}
export const BOM_STATUS_TAGS: Record<BomStatus, TagType> = {
  DRAFT: 'info',
  RELEASED: 'success',
  OBSOLETE: 'danger',
}
export const BOM_STATUS_OPTIONS = toOptions(BOM_STATUS_LABELS)

export const ROUTING_STATUS_LABELS: Record<RoutingStatus, string> = BOM_STATUS_LABELS
export const ROUTING_STATUS_TAGS: Record<RoutingStatus, TagType> = BOM_STATUS_TAGS
export const ROUTING_STATUS_OPTIONS = toOptions(ROUTING_STATUS_LABELS)

// --------------------------------------------------------------------------- #
// 组织与人员
// --------------------------------------------------------------------------- #
export const ORG_TYPE_LABELS: Record<OrgType, string> = {
  COMPANY: '公司',
  DEPT: '部门',
  TEAM: '班组',
}
export const ORG_TYPE_TAGS: Record<OrgType, TagType> = {
  COMPANY: 'primary',
  DEPT: 'success',
  TEAM: 'info',
}
export const ORG_TYPE_OPTIONS = toOptions(ORG_TYPE_LABELS)

export const EMPLOYEE_STATUS_LABELS: Record<EmployeeStatus, string> = {
  ACTIVE: '在职',
  INACTIVE: '离职',
  LEAVE: '休假',
}
export const EMPLOYEE_STATUS_TAGS: Record<EmployeeStatus, TagType> = {
  ACTIVE: 'success',
  INACTIVE: 'info',
  LEAVE: 'warning',
}
export const EMPLOYEE_STATUS_OPTIONS = toOptions(EMPLOYEE_STATUS_LABELS)

export const GENDER_LABELS: Record<Gender, string> = {
  MALE: '男',
  FEMALE: '女',
  UNKNOWN: '未知',
}
export const GENDER_OPTIONS = toOptions(GENDER_LABELS)

// --------------------------------------------------------------------------- #
// 权限
// --------------------------------------------------------------------------- #
export const PERMISSION_TYPE_LABELS: Record<PermissionType, string> = {
  MENU: '菜单',
  BUTTON: '按钮',
  API: '接口',
}
export const PERMISSION_TYPE_TAGS: Record<PermissionType, TagType> = {
  MENU: 'primary',
  BUTTON: 'warning',
  API: 'info',
}
export const PERMISSION_TYPE_OPTIONS = toOptions(PERMISSION_TYPE_LABELS)

export const DATA_SCOPE_LABELS: Record<DataScope, string> = {
  ALL: '全部数据',
  ORG: '本组织',
  ORG_AND_CHILD: '本组织及下级',
  SELF: '仅本人',
  CUSTOM: '自定义',
}
export const DATA_SCOPE_OPTIONS = toOptions(DATA_SCOPE_LABELS)

// --------------------------------------------------------------------------- #
// 操作日志
// --------------------------------------------------------------------------- #
export const OPERATION_ACTION_LABELS: Record<OperationAction, string> = {
  CREATE: '新增',
  UPDATE: '修改',
  DELETE: '删除',
  QUERY: '查询',
  LOGIN: '登录',
  LOGOUT: '登出',
  OTHER: '其它',
}
export const OPERATION_ACTION_TAGS: Record<OperationAction, TagType> = {
  CREATE: 'success',
  UPDATE: 'primary',
  DELETE: 'danger',
  QUERY: 'info',
  LOGIN: 'warning',
  LOGOUT: 'info',
  OTHER: 'info',
}
export const OPERATION_ACTION_OPTIONS = toOptions(OPERATION_ACTION_LABELS)

export const LOG_STATUS_LABELS: Record<LogStatus, string> = {
  SUCCESS: '成功',
  FAIL: '失败',
}
export const LOG_STATUS_TAGS: Record<LogStatus, TagType> = {
  SUCCESS: 'success',
  FAIL: 'danger',
}
export const LOG_STATUS_OPTIONS = toOptions(LOG_STATUS_LABELS)
