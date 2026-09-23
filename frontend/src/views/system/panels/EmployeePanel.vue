<script setup lang="ts">
/**
 * 人员档案维护（组织与人员信息管理）。
 *
 * 标准列表页结构：查询条件 → 工具栏 → 表格 → 分页 → 新增 / 编辑弹窗。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createEmployee,
  deleteEmployee,
  getOrganizationTree,
  listEmployees,
  updateEmployee,
} from '@/api/system'
import type {
  Employee,
  EmployeePayload,
  EmployeeQuery,
  OrganizationTree,
} from '@/api/system/types'
import {
  EMPLOYEE_STATUS_LABELS,
  EMPLOYEE_STATUS_OPTIONS,
  EMPLOYEE_STATUS_TAGS,
  GENDER_LABELS,
  GENDER_OPTIONS,
} from '@/views/system/options'

const loading = ref(false)
const rows = ref<Employee[]>([])
const total = ref(0)

/** 组织下拉选项：组织树扁平化后的结果 */
const orgOptions = ref<{ id: number; label: string }[]>([])

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  org_id: undefined as number | undefined,
  status: '' as EmployeeQuery['status'] | '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): EmployeeQuery {
  const params: EmployeeQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.org_id) params.org_id = query.org_id
  if (query.status) params.status = query.status
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listEmployees(buildQuery())
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
  query.org_id = undefined
  query.status = ''
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 组织下拉选项
// --------------------------------------------------------------------------- #
/** 把组织树拍平成选项，label 用「上级 / 下级」表达层级 */
function flattenTree(nodes: OrganizationTree[], prefix = ''): { id: number; label: string }[] {
  const options: { id: number; label: string }[] = []
  for (const node of nodes) {
    const label = prefix ? `${prefix} / ${node.name}` : node.name
    options.push({ id: node.id, label })
    options.push(...flattenTree(node.children, label))
  }
  return options
}

async function loadOrgOptions() {
  try {
    orgOptions.value = flattenTree(await getOrganizationTree())
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
  code: '',
  name: '',
  gender: 'UNKNOWN' as EmployeePayload['gender'],
  phone: '',
  email: '',
  org_id: undefined as number | undefined,
  position: '',
  hire_date: '',
  status: 'ACTIVE' as EmployeePayload['status'],
  remark: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.gender = 'UNKNOWN'
  form.phone = ''
  form.email = ''
  form.org_id = undefined
  form.position = ''
  form.hire_date = ''
  form.status = 'ACTIVE'
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Employee) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.gender = row.gender
  form.phone = row.phone ?? ''
  form.email = row.email ?? ''
  form.org_id = row.org_id ?? undefined
  form.position = row.position ?? ''
  form.hire_date = row.hire_date ?? ''
  form.status = row.status
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildPayload(): EmployeePayload {
  return {
    code: form.code,
    name: form.name,
    gender: form.gender,
    phone: form.phone || null,
    email: form.email || null,
    org_id: form.org_id ?? null,
    position: form.position || null,
    hire_date: form.hire_date || null,
    status: form.status,
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
      await createEmployee(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateEmployee(editingId.value, buildPayload())
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

async function handleDelete(row: Employee) {
  await ElMessageBox.confirm(`确定删除人员「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteEmployee(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(() => {
  load()
  loadOrgOptions()
})
</script>

<template>
  <div>
    <el-form :inline="true" class="panel__query">
      <el-form-item label="关键词">
        <el-input
          v-model="query.keyword"
          placeholder="工号 / 姓名 / 手机号 / 岗位"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="所属组织">
        <el-select v-model="query.org_id" placeholder="全部" clearable filterable style="width: 190px">
          <el-option
            v-for="item in orgOptions"
            :key="item.id"
            :label="item.label"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="在职状态">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 120px">
          <el-option
            v-for="item in EMPLOYEE_STATUS_OPTIONS"
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
      <el-button type="primary" @click="openCreate">新增人员</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="工号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column label="性别" width="70">
        <template #default="{ row }">{{ GENDER_LABELS[row.gender as keyof typeof GENDER_LABELS] }}</template>
      </el-table-column>
      <el-table-column prop="phone" label="手机号" width="130" />
      <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
      <el-table-column prop="org_name" label="所属组织" min-width="140" show-overflow-tooltip />
      <el-table-column prop="position" label="岗位" min-width="120" show-overflow-tooltip />
      <el-table-column prop="hire_date" label="入职日期" width="110" />
      <el-table-column label="在职状态" width="90">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="EMPLOYEE_STATUS_TAGS[row.status as keyof typeof EMPLOYEE_STATUS_TAGS]"
          >
            {{ EMPLOYEE_STATUS_LABELS[row.status as keyof typeof EMPLOYEE_STATUS_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
      :title="editingId === null ? '新增人员' : '编辑人员'"
      width="620px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="工号" prop="code">
              <el-input v-model="form.code" placeholder="如 E-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="name">
              <el-input v-model="form.name" placeholder="如 张三" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="性别">
              <el-select v-model="form.gender" style="width: 100%">
                <el-option
                  v-for="item in GENDER_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="手机号">
              <el-input v-model="form.phone" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属组织">
              <el-select v-model="form.org_id" clearable filterable style="width: 100%">
                <el-option
                  v-for="item in orgOptions"
                  :key="item.id"
                  :label="item.label"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="岗位">
              <el-input v-model="form.position" placeholder="如 装配工" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="入职日期">
              <el-date-picker
                v-model="form.hire_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="在职状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="item in EMPLOYEE_STATUS_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
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
</style>
