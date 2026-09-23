/**
 * system 模块（系统与基础信息管理）类型定义。
 *
 * 与后端 `app/modules/system/schemas.py` 一一对应：
 * - 枚举在后端以字符串返回，这里用字符串字面量联合类型表达；
 * - `*Payload` 对应后端的 `XxxCreate`，更新时统一用 `Partial<*Payload>` 对应 `XxxUpdate`；
 * - 出参中的 `xxx_name` / `xxx_ids` 是后端回填的增强字段（只读）。
 */

import type { PageQuery } from '@/types/api'

// --------------------------------------------------------------------------- #
// 枚举
// --------------------------------------------------------------------------- #
export type CommonStatus = 'ENABLED' | 'DISABLED'
export type OrgType = 'COMPANY' | 'DEPT' | 'TEAM'
export type EmployeeStatus = 'ACTIVE' | 'INACTIVE' | 'LEAVE'
export type Gender = 'MALE' | 'FEMALE' | 'UNKNOWN'
export type MaterialType = 'RAW' | 'SEMI' | 'FINISHED' | 'PACK'
export type SourceType = 'PURCHASE' | 'MAKE'
export type BomStatus = 'DRAFT' | 'RELEASED' | 'OBSOLETE'
export type BomType = 'DESIGN' | 'MANUFACTURE' | 'SALE'
export type RoutingStatus = 'DRAFT' | 'RELEASED' | 'OBSOLETE'
export type PermissionType = 'MENU' | 'BUTTON' | 'API'
export type DataScope = 'ALL' | 'ORG' | 'ORG_AND_CHILD' | 'SELF' | 'CUSTOM'
export type OperationAction = 'CREATE' | 'UPDATE' | 'DELETE' | 'QUERY' | 'LOGIN' | 'LOGOUT' | 'OTHER'
export type LogStatus = 'SUCCESS' | 'FAIL'
export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED'

// --------------------------------------------------------------------------- #
// 一、产品信息：物料主数据 / BOM（成品、半成品、原材料统一用 Material 表达）
// --------------------------------------------------------------------------- #
export interface Material {
  id: number
  code: string
  name: string
  spec?: string | null
  model?: string | null
  unit: string
  category_code?: string | null
  material_type: MaterialType
  source_type: SourceType
  standard_cost?: number | null
  safety_stock?: number | null
  lead_time_days?: number | null
  status: CommonStatus
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface MaterialPayload {
  code: string
  name: string
  spec?: string | null
  model?: string | null
  unit?: string
  category_code?: string | null
  material_type?: MaterialType
  source_type?: SourceType
  standard_cost?: number | null
  safety_stock?: number | null
  lead_time_days?: number | null
  status?: CommonStatus
  remark?: string | null
}

export interface MaterialQuery extends PageQuery {
  keyword?: string
  category_code?: string
  material_type?: MaterialType
  source_type?: SourceType
  status?: CommonStatus
}

export interface Bom {
  id: number
  code: string
  parent_material_id: number
  bom_type: BomType
  version: string
  base_qty: number
  status: BomStatus
  effective_from?: string | null
  effective_to?: string | null
  remark?: string | null
  /** 后端回填：父件物料编码 */
  parent_material_code?: string | null
  /** 后端回填：父件物料名称 */
  parent_material_name?: string | null
  /** 后端回填：BOM 行数 */
  line_count: number
  created_at: string
  updated_at: string
}

export interface BomPayload {
  code: string
  parent_material_id: number
  bom_type?: BomType
  version?: string
  base_qty?: number
  status?: BomStatus
  effective_from?: string | null
  effective_to?: string | null
  remark?: string | null
}

export interface BomQuery extends PageQuery {
  keyword?: string
  parent_material_id?: number
  bom_type?: BomType
  status?: BomStatus
}

export interface BomLine {
  id: number
  bom_id: number
  line_no: number
  child_material_id: number
  quantity: number
  unit?: string | null
  loss_rate: number
  position?: string | null
  is_phantom: boolean
  is_optional: boolean
  option_group?: string | null
  substitute_group?: string | null
  substitute_priority: number
  remark?: string | null
  /** 后端回填：子件物料编码 / 名称 / 规格 */
  material_code?: string | null
  material_name?: string | null
  material_spec?: string | null
}

export interface BomLinePayload {
  line_no?: number
  child_material_id: number
  quantity?: number
  unit?: string | null
  loss_rate?: number
  position?: string | null
  is_phantom?: boolean
  is_optional?: boolean
  option_group?: string | null
  substitute_group?: string | null
  substitute_priority?: number
  remark?: string | null
}

export interface BomDetail extends Bom {
  lines: BomLine[]
}

/** 多层 BOM 展开后的一个节点（树形接口与一维清单接口共用） */
export interface BomTreeNode {
  material_id: number
  material_code: string
  material_name: string
  spec?: string | null
  model?: string | null
  unit: string
  /** 层级号，顶层为 1 */
  level: number
  /** 本行用量（上层产出 1 个父件需要的数量） */
  quantity: number
  /** 累计用量 = 沿路径连乘，顶层为 1 */
  acc_quantity: number
  is_phantom: boolean
  is_optional: boolean
  option_group?: string | null
  substitute_group?: string | null
  substitute_priority: number
  children: BomTreeNode[]
}

export interface BomExpandQuery {
  bom_type?: BomType
  on_date?: string
}

// --------------------------------------------------------------------------- #
// 二、工艺信息：工艺路线 / 工序
// --------------------------------------------------------------------------- #
export interface Routing {
  id: number
  code: string
  material_id: number
  name: string
  version: string
  is_default: boolean
  status: RoutingStatus
  remark?: string | null
  /** 后端回填：适用物料编码 / 名称 */
  material_code?: string | null
  material_name?: string | null
  /** 后端回填：工序数与单件总工时 */
  step_count: number
  total_minutes?: number | null
  created_at: string
  updated_at: string
}

export interface RoutingPayload {
  code: string
  material_id: number
  name: string
  version?: string
  is_default?: boolean
  status?: RoutingStatus
  remark?: string | null
}

export interface RoutingQuery extends PageQuery {
  keyword?: string
  material_id?: number
  status?: RoutingStatus
}

export interface RoutingStep {
  id: number
  routing_id: number
  step_no: number
  step_code?: string | null
  step_name: string
  work_center?: string | null
  equipment?: string | null
  setup_minutes?: number | null
  run_minutes?: number | null
  is_key: boolean
  remark?: string | null
}

export interface RoutingStepPayload {
  step_no?: number
  step_code?: string | null
  step_name: string
  work_center?: string | null
  equipment?: string | null
  setup_minutes?: number | null
  run_minutes?: number | null
  is_key?: boolean
  remark?: string | null
}

export interface RoutingDetail extends Routing {
  steps: RoutingStep[]
}

// --------------------------------------------------------------------------- #
// 三、组织与人员
// --------------------------------------------------------------------------- #
export interface Organization {
  id: number
  code: string
  name: string
  parent_id?: number | null
  /** 层级路径，形如 /1/3/ */
  path: string
  level: number
  org_type: OrgType
  leader?: string | null
  phone?: string | null
  sort_order: number
  is_enabled: boolean
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface OrganizationPayload {
  code: string
  name: string
  parent_id?: number | null
  org_type?: OrgType
  leader?: string | null
  phone?: string | null
  sort_order?: number
  is_enabled?: boolean
  remark?: string | null
}

export interface OrganizationQuery extends PageQuery {
  keyword?: string
  parent_id?: number
  org_type?: OrgType
  is_enabled?: boolean
}

export interface OrganizationTree extends Organization {
  children: OrganizationTree[]
}

export interface Employee {
  id: number
  code: string
  name: string
  gender: Gender
  phone?: string | null
  email?: string | null
  org_id?: number | null
  position?: string | null
  hire_date?: string | null
  status: EmployeeStatus
  remark?: string | null
  /** 后端回填：所属组织名称 */
  org_name?: string | null
  created_at: string
  updated_at: string
}

export interface EmployeePayload {
  code: string
  name: string
  gender?: Gender
  phone?: string | null
  email?: string | null
  org_id?: number | null
  position?: string | null
  hire_date?: string | null
  status?: EmployeeStatus
  remark?: string | null
}

export interface EmployeeQuery extends PageQuery {
  keyword?: string
  org_id?: number
  status?: EmployeeStatus
}

// --------------------------------------------------------------------------- #
// 四、共性基础字典
// --------------------------------------------------------------------------- #
export interface DictionaryType {
  id: number
  code: string
  name: string
  /** 系统内置字典，禁止删除 */
  is_system: boolean
  is_enabled: boolean
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface DictionaryTypePayload {
  code: string
  name: string
  is_enabled?: boolean
  remark?: string | null
}

export interface DictionaryTypeQuery extends PageQuery {
  keyword?: string
  is_enabled?: boolean
}

export interface DictionaryItem {
  id: number
  type_id: number
  parent_id?: number | null
  item_code: string
  item_label: string
  item_value?: string | null
  sort_order: number
  is_enabled: boolean
  extra?: Record<string, unknown> | null
  remark?: string | null
  /** 后端回填：所属字典类型编码 */
  type_code?: string | null
  created_at: string
  updated_at: string
}

export interface DictionaryItemPayload {
  item_code: string
  item_label: string
  parent_id?: number | null
  item_value?: string | null
  sort_order?: number
  is_enabled?: boolean
  extra?: Record<string, unknown> | null
  remark?: string | null
}

export interface DictionaryItemQuery extends PageQuery {
  keyword?: string
  type_id?: number
  is_enabled?: boolean
}

// --------------------------------------------------------------------------- #
// 五、系统访问权限：账号 / 角色 / 权限
// --------------------------------------------------------------------------- #
export interface User {
  id: number
  username: string
  real_name?: string | null
  employee_id?: number | null
  org_id?: number | null
  email?: string | null
  phone?: string | null
  is_superuser: boolean
  is_enabled: boolean
  /** 注册审批状态：PENDING 只有游客权限，APPROVED 后自选角色生效，REJECTED 不能登录 */
  approval_status: ApprovalStatus
  remark?: string | null
  role_ids: number[]
  role_names: string[]
  org_name?: string | null
  employee_name?: string | null
  last_login_at?: string | null
  created_at: string
  updated_at: string
}

export interface UserPayload {
  username: string
  password: string
  real_name?: string | null
  employee_id?: number | null
  org_id?: number | null
  email?: string | null
  phone?: string | null
  is_superuser?: boolean
  is_enabled?: boolean
  remark?: string | null
  role_ids?: number[]
}

/** 修改账号时不允许改账号名与密码，与后端 `UserUpdate` 一致 */
export type UserUpdatePayload = Partial<Omit<UserPayload, 'username' | 'password' | 'role_ids'>>

export interface UserQuery extends PageQuery {
  keyword?: string
  org_id?: number
  is_enabled?: boolean
  is_superuser?: boolean
  approval_status?: ApprovalStatus
}

export interface Role {
  id: number
  code: string
  name: string
  data_scope: DataScope
  sort_order: number
  is_enabled: boolean
  description?: string | null
  permission_ids: number[]
  created_at: string
  updated_at: string
}

export interface RolePayload {
  code: string
  name: string
  data_scope?: DataScope
  sort_order?: number
  is_enabled?: boolean
  description?: string | null
  permission_ids?: number[]
}

export interface RoleQuery extends PageQuery {
  keyword?: string
  is_enabled?: boolean
}

export interface Permission {
  id: number
  code: string
  name: string
  perm_type: PermissionType
  parent_id?: number | null
  path?: string | null
  method?: string | null
  sort_order: number
  is_enabled: boolean
  created_at: string
  updated_at: string
}

export interface PermissionPayload {
  code: string
  name: string
  perm_type?: PermissionType
  parent_id?: number | null
  path?: string | null
  method?: string | null
  sort_order?: number
  is_enabled?: boolean
}

export interface PermissionQuery extends PageQuery {
  keyword?: string
  perm_type?: PermissionType
  parent_id?: number
}

export interface PermissionTree extends Permission {
  children: PermissionTree[]
}

// --------------------------------------------------------------------------- #
// 六、系统操作日志
// --------------------------------------------------------------------------- #
export interface OperationLog {
  id: number
  user_id?: number | null
  username?: string | null
  module?: string | null
  action: OperationAction
  description?: string | null
  method?: string | null
  path?: string | null
  ip?: string | null
  request_params?: string | null
  status: LogStatus
  error_msg?: string | null
  duration_ms?: number | null
  created_at: string
}

export interface OperationLogQuery extends PageQuery {
  keyword?: string
  module?: string
  action?: OperationAction
  status?: LogStatus
  username?: string
  created_from?: string
  created_to?: string
}

// --------------------------------------------------------------------------- #
// 七、认证
// --------------------------------------------------------------------------- #
export interface LoginPayload {
  username: string
  password: string
}

export interface LoginUser {
  id: number
  username: string
  real_name?: string | null
  is_superuser: boolean
  org_id?: number | null
  /** 注册审批状态：PENDING 时 roles/permissions 只含游客权限 */
  approval_status: ApprovalStatus
  roles: string[]
  permissions: string[]
}

export interface TokenData {
  access_token: string
  token_type: string
  expires_in: number
  user: LoginUser
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

/** 注册页可自选的身份（后端返回启用中的角色） */
export interface RoleOption {
  id: number
  code: string
  name: string
}

/** 公开注册：自选身份，审批通过后生效 */
export interface RegisterPayload {
  username: string
  password: string
  real_name?: string | null
  email?: string | null
  phone?: string | null
  role_id: number
}
