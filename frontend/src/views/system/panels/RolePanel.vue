<script setup lang="ts">
/**
 * 角色与访问范围管理（系统访问权限管理）。
 *
 * 标准列表页结构：查询条件 → 工具栏 → 表格 → 分页 → 新增 / 编辑弹窗，
 * 另有「分配权限」弹窗（权限资源树 + 勾选）。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules, TreeInstance } from 'element-plus'
import { nextTick, onMounted, reactive, ref } from 'vue'

import {
  assignRolePermissions,
  createRole,
  deleteRole,
  getPermissionTree,
  listRoles,
  updateRole,
} from '@/api/system'
import type { CommonStatus, PermissionTree, Role, RolePayload, RoleQuery } from '@/api/system/types'
import {
  COMMON_STATUS_LABELS,
  COMMON_STATUS_OPTIONS,
  COMMON_STATUS_TAGS,
  DATA_SCOPE_LABELS,
  DATA_SCOPE_OPTIONS,
  PERMISSION_TYPE_LABELS,
  PERMISSION_TYPE_TAGS,
} from '@/views/system/options'

const loading = ref(false)
const rows = ref<Role[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  is_enabled: '' as CommonStatus | '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): RoleQuery {
  const params: RoleQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.is_enabled) params.is_enabled = query.is_enabled === 'ENABLED'
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listRoles(buildQuery())
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
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 新增 / 编辑
// --------------------------------------------------------------------------- #
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  code: '',
  name: '',
  data_scope: 'ALL' as RolePayload['data_scope'],
  sort_order: 0,
  is_enabled: true,
  description: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入角色编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.data_scope = 'ALL'
  form.sort_order = 0
  form.is_enabled = true
  form.description = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Role) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.data_scope = row.data_scope
  form.sort_order = row.sort_order
  form.is_enabled = row.is_enabled
  form.description = row.description ?? ''
  dialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildPayload(): RolePayload {
  return {
    code: form.code,
    name: form.name,
    data_scope: form.data_scope,
    sort_order: form.sort_order,
    is_enabled: form.is_enabled,
    description: form.description || null,
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
      await createRole(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateRole(editingId.value, buildPayload())
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

async function handleDelete(row: Role) {
  await ElMessageBox.confirm(`确定删除角色「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteRole(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 分配权限
// --------------------------------------------------------------------------- #
const permDialogVisible = ref(false)
const permSubmitting = ref(false)
const permLoading = ref(false)
const permissionTree = ref<PermissionTree[]>([])
const currentRole = ref<Role | null>(null)
const treeRef = ref<TreeInstance>()

async function openAssignPermissions(row: Role) {
  currentRole.value = row
  permDialogVisible.value = true
  permLoading.value = true
  try {
    permissionTree.value = await getPermissionTree()
    // 等树渲染完成后再回显角色已有的权限勾选状态
    await nextTick()
    treeRef.value?.setCheckedKeys(row.permission_ids, false)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    permLoading.value = false
  }
}

async function handleAssignPermissions() {
  if (currentRole.value === null) {
    return
  }

  // 树启用了 check-strictly（父子不联动），已勾选节点即为授权结果
  const checkedKeys = treeRef.value?.getCheckedKeys() ?? []
  const permissionIds = checkedKeys.map((key) => Number(key))

  permSubmitting.value = true
  try {
    await assignRolePermissions(currentRole.value.id, permissionIds)
    ElMessage.success('权限分配成功')
    permDialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    permSubmitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <el-form :inline="true" class="panel__query">
      <el-form-item label="关键词">
        <el-input
          v-model="query.keyword"
          placeholder="编码 / 名称"
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
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <div class="panel__toolbar">
      <el-button type="primary" @click="openCreate">新增角色</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="角色编码" width="140" />
      <el-table-column prop="name" label="角色名称" width="140" />
      <el-table-column label="访问范围" width="120">
        <template #default="{ row }">
          <el-tag size="small" type="primary">
            {{ DATA_SCOPE_LABELS[row.data_scope as keyof typeof DATA_SCOPE_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="sort_order" label="排序" width="70" />
      <el-table-column label="是否启用" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="COMMON_STATUS_TAGS[row.is_enabled ? 'ENABLED' : 'DISABLED']">
            {{ COMMON_STATUS_LABELS[row.is_enabled ? 'ENABLED' : 'DISABLED'] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openAssignPermissions(row)">分配权限</el-button>
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
      :title="editingId === null ? '新增角色' : '编辑角色'"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="角色编码" prop="code">
          <el-input v-model="form.code" placeholder="如 system_admin" />
        </el-form-item>
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="如 系统管理员" />
        </el-form-item>
        <el-form-item label="访问范围">
          <el-select v-model="form.data_scope" style="width: 100%">
            <el-option
              v-for="item in DATA_SCOPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="permDialogVisible"
      :title="`分配权限${currentRole ? `：${currentRole.name}` : ''}`"
      width="560px"
      top="6vh"
    >
      <div v-loading="permLoading" class="panel__tree">
        <el-tree
          ref="treeRef"
          :data="permissionTree"
          node-key="id"
          show-checkbox
          check-strictly
          default-expand-all
          :props="{ label: 'name', children: 'children' }"
        >
          <template #default="{ data }">
            <span class="panel__node">
              <span>{{ data.name }}</span>
              <el-tag
                size="small"
                :type="PERMISSION_TYPE_TAGS[data.perm_type as keyof typeof PERMISSION_TYPE_TAGS]"
              >
                {{ PERMISSION_TYPE_LABELS[data.perm_type as keyof typeof PERMISSION_TYPE_LABELS] }}
              </el-tag>
            </span>
          </template>
        </el-tree>
      </div>

      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="permSubmitting" @click="handleAssignPermissions">
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

.panel__tree {
  max-height: 60vh;
  overflow: auto;
}

.panel__node {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
