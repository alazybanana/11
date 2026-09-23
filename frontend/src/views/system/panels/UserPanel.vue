<script setup lang="ts">
/**
 * 账号管理（系统访问权限管理）。
 *
 * 标准列表页结构：查询条件 → 工具栏 → 表格 → 分页 → 新增 / 编辑弹窗，
 * 另有「分配角色」与「重置密码」两个独立操作。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  approveUser,
  assignUserRoles,
  createUser,
  deleteUser,
  getOrganizationTree,
  listRoles,
  listUsers,
  rejectUser,
  resetUserPassword,
  updateUser,
} from '@/api/system'
import type {
  ApprovalStatus,
  CommonStatus,
  OrganizationTree,
  Role,
  User,
  UserPayload,
  UserQuery,
  UserUpdatePayload,
} from '@/api/system/types'
import { useAuthStore } from '@/stores/modules/auth'
import {
  COMMON_STATUS_LABELS,
  COMMON_STATUS_OPTIONS,
  COMMON_STATUS_TAGS,
} from '@/views/system/options'

const authStore = useAuthStore()

/** 只有人事主管（已批准）或超级管理员能审批注册 */
const canApprove = computed(
  () => authStore.isSuperuser || authStore.user?.roles.includes('HR_MANAGER') === true,
)

/** 注册审批状态展示映射 */
const APPROVAL_STATUS_LABELS: Record<ApprovalStatus, string> = {
  PENDING: '待审批',
  APPROVED: '已批准',
  REJECTED: '已驳回',
}

const APPROVAL_STATUS_TAGS: Record<ApprovalStatus, 'warning' | 'success' | 'danger'> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
}

const APPROVAL_STATUS_OPTIONS = (Object.keys(APPROVAL_STATUS_LABELS) as ApprovalStatus[]).map(
  (value) => ({ value, label: APPROVAL_STATUS_LABELS[value] }),
)

const loading = ref(false)
const rows = ref<User[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  is_enabled: '' as CommonStatus | '',
  is_superuser: '' as UserQuery['is_superuser'] | '',
  approval_status: '' as ApprovalStatus | '',
})

/** 布尔型查询条件的下拉选项 */
const BOOL_OPTIONS = [
  { label: '是', value: true },
  { label: '否', value: false },
]

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): UserQuery {
  const params: UserQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.is_enabled) params.is_enabled = query.is_enabled === 'ENABLED'
  if (query.is_superuser !== '') params.is_superuser = query.is_superuser
  if (query.approval_status) params.approval_status = query.approval_status
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listUsers(buildQuery())
    rows.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  query.page = 1
  load()
}

function handleReset() {
  query.keyword = ''
  query.is_enabled = ''
  query.is_superuser = ''
  query.approval_status = ''
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 组织 / 角色下拉数据
// --------------------------------------------------------------------------- #
interface OrgOption {
  id: number
  name: string
}

const orgOptions = ref<OrgOption[]>([])
const roleOptions = ref<Role[]>([])

/** 把组织树拍平成下拉选项，用缩进体现层级 */
function flattenOrgs(nodes: OrganizationTree[], depth: number, options: OrgOption[]): void {
  nodes.forEach((node) => {
    options.push({ id: node.id, name: `${'　'.repeat(depth)}${node.name}` })
    flattenOrgs(node.children ?? [], depth + 1, options)
  })
}

async function loadOrgOptions() {
  try {
    const tree = await getOrganizationTree()
    const options: OrgOption[] = []
    flattenOrgs(tree, 0, options)
    orgOptions.value = options
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

async function loadRoleOptions() {
  try {
    const data = await listRoles({ page: 1, page_size: 200 })
    roleOptions.value = data.items
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

// --------------------------------------------------------------------------- #
// 新增 / 编辑
// --------------------------------------------------------------------------- #
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  org_id: undefined as number | undefined,
  email: '',
  phone: '',
  is_superuser: false,
  is_enabled: true,
  remark: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入初始密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6~64 位', trigger: 'blur' },
  ],
}

function resetForm() {
  form.username = ''
  form.password = ''
  form.real_name = ''
  form.org_id = undefined
  form.email = ''
  form.phone = ''
  form.is_superuser = false
  form.is_enabled = true
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: User) {
  editingId.value = row.id
  form.username = row.username
  form.password = ''
  form.real_name = row.real_name ?? ''
  form.org_id = row.org_id ?? undefined
  form.email = row.email ?? ''
  form.phone = row.phone ?? ''
  form.is_superuser = row.is_superuser
  form.is_enabled = row.is_enabled
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildPayload(): UserPayload {
  return {
    username: form.username,
    password: form.password,
    real_name: form.real_name || null,
    org_id: form.org_id ?? null,
    email: form.email || null,
    phone: form.phone || null,
    is_superuser: form.is_superuser,
    is_enabled: form.is_enabled,
    remark: form.remark || null,
  }
}

/** 修改账号时不允许提交账号名与密码，因此单独构造更新载荷 */
function buildUpdatePayload(): UserUpdatePayload {
  return {
    real_name: form.real_name || null,
    org_id: form.org_id ?? null,
    email: form.email || null,
    phone: form.phone || null,
    is_superuser: form.is_superuser,
    is_enabled: form.is_enabled,
    remark: form.remark || null,
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  submitting.value = true
  try {
    if (editingId.value === null) {
      await createUser(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateUser(editingId.value, buildUpdatePayload())
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: User) {
  await ElMessageBox.confirm(`确定删除账号「${row.username}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteUser(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 注册审批（批准 / 驳回）
// --------------------------------------------------------------------------- #
async function handleApprove(row: User) {
  await ElMessageBox.confirm(
    `确定批准账号「${row.username}」吗？批准后其将获得申请的角色权限。`,
    '批准注册',
    { type: 'warning' },
  )
    .then(async () => {
      try {
        await approveUser(row.id)
        ElMessage.success(`已批准「${row.username}」`)
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

async function handleReject(row: User) {
  await ElMessageBox.confirm(
    `确定驳回「${row.username}」的注册申请吗？驳回后该账号将无法再登录。`,
    '驳回注册',
    { type: 'warning' },
  )
    .then(async () => {
      try {
        await rejectUser(row.id)
        ElMessage.success(`已驳回「${row.username}」`)
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 分配角色
// --------------------------------------------------------------------------- #
const roleDialogVisible = ref(false)
const roleSubmitting = ref(false)
const currentUser = ref<User | null>(null)
const selectedRoleIds = ref<number[]>([])

function openAssignRoles(row: User) {
  currentUser.value = row
  selectedRoleIds.value = [...row.role_ids]
  roleDialogVisible.value = true
}

async function handleAssignRoles() {
  if (currentUser.value === null) {
    return
  }

  roleSubmitting.value = true
  try {
    await assignUserRoles(currentUser.value.id, selectedRoleIds.value)
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    roleSubmitting.value = false
  }
}

// --------------------------------------------------------------------------- #
// 重置密码
// --------------------------------------------------------------------------- #
function handleResetPassword(row: User) {
  ElMessageBox.prompt(`请输入账号「${row.username}」的新密码`, '重置密码', {
    inputType: 'password',
    inputPattern: /^.{6,64}$/,
    inputErrorMessage: '密码长度需为 6~64 位',
  })
    .then(async ({ value }) => {
      try {
        await resetUserPassword(row.id, value)
        ElMessage.success('密码重置成功')
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(() => {
  load()
  loadOrgOptions()
  loadRoleOptions()
})
</script>

<template>
  <div>
    <el-form :inline="true" class="panel__query">
      <el-form-item label="关键词">
        <el-input
          v-model="query.keyword"
          placeholder="账号 / 姓名 / 邮箱 / 手机号"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="是否启用">
        <el-select v-model="query.is_enabled" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in COMMON_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="是否超管">
        <el-select v-model="query.is_superuser" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in BOOL_OPTIONS"
            :key="item.label"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="审批状态">
        <el-select v-model="query.approval_status" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in APPROVAL_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <div class="panel__toolbar">
      <el-button type="primary" @click="openCreate">新增账号</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="username" label="登录账号" width="120" />
      <el-table-column prop="real_name" label="姓名" width="100" />
      <el-table-column prop="org_name" label="所属组织" width="140" show-overflow-tooltip />
      <el-table-column label="角色" min-width="180">
        <template #default="{ row }">
          <template v-if="row.role_names.length > 0">
            <el-tag v-for="name in row.role_names" :key="name" size="small" class="panel__tag">
              {{ name }}
            </el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="是否超管" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_superuser ? 'danger' : 'info'">
            {{ row.is_superuser ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_login_at" label="最后登录时间" width="160" />
      <el-table-column label="审批状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="APPROVAL_STATUS_TAGS[row.approval_status as ApprovalStatus]">
            {{ APPROVAL_STATUS_LABELS[row.approval_status as ApprovalStatus] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="是否启用" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="COMMON_STATUS_TAGS[row.is_enabled ? 'ENABLED' : 'DISABLED']">
            {{ COMMON_STATUS_LABELS[row.is_enabled ? 'ENABLED' : 'DISABLED'] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="330" fixed="right">
        <template #default="{ row }">
          <template v-if="row.approval_status === 'PENDING' && canApprove">
            <el-button link type="success" @click="handleApprove(row)">批准</el-button>
            <el-button link type="danger" @click="handleReject(row)">驳回</el-button>
          </template>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openAssignRoles(row)">分配角色</el-button>
          <el-button link type="warning" @click="handleResetPassword(row)">重置密码</el-button>
          <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="panel__pagination"
      background
      layout="total, sizes, prev, pager, next"
      :total="total"
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :page-sizes="[10, 20, 50, 100]"
      @current-change="load"
      @size-change="handleSearch"
    />

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新增账号' : '编辑账号'"
      width="620px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="登录账号" prop="username">
              <el-input
                v-model="form.username"
                placeholder="如 zhangsan"
                :disabled="editingId !== null"
              />
            </el-form-item>
          </el-col>
          <el-col v-if="editingId === null" :span="12">
            <el-form-item label="初始密码" prop="password">
              <el-input v-model="form.password" type="password" placeholder="6~64 位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名">
              <el-input v-model="form.real_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属组织">
              <el-select v-model="form.org_id" placeholder="请选择组织" clearable style="width: 100%">
                <el-option
                  v-for="item in orgOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="超级管理员">
              <el-switch v-model="form.is_superuser" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否启用">
              <el-switch v-model="form.is_enabled" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" title="分配角色" width="420px">
      <el-select
        v-model="selectedRoleIds"
        multiple
        placeholder="请选择角色"
        style="width: 100%"
      >
        <el-option
          v-for="role in roleOptions"
          :key="role.id"
          :label="`${role.name}(${role.code})`"
          :value="role.id"
        />
      </el-select>

      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="roleSubmitting" @click="handleAssignRoles">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.panel__query {
  margin-bottom: 4px;
}

.panel__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.panel__count {
  font-size: 13px;
  color: #909399;
}

.panel__pagination {
  margin-top: 12px;
  justify-content: flex-end;
}

.panel__tag {
  margin-right: 4px;
}
</style>
