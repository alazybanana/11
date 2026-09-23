<script setup lang="ts">
/**
 * 工艺路线维护（工艺路线头 + 工序明细）。
 *
 * 列表页维护工艺路线；「维护工序」弹窗内维护工序明细。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createRouting,
  createRoutingStep,
  deleteRouting,
  deleteRoutingStep,
  getRoutingDetail,
  listMaterials,
  listRoutings,
  updateRouting,
  updateRoutingStep,
} from '@/api/system'
import type {
  Material,
  Routing,
  RoutingPayload,
  RoutingQuery,
  RoutingStep,
  RoutingStepPayload,
} from '@/api/system/types'
import {
  ROUTING_STATUS_LABELS,
  ROUTING_STATUS_OPTIONS,
  ROUTING_STATUS_TAGS,
} from '@/views/system/options'

const loading = ref(false)
const rows = ref<Routing[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: '' as RoutingQuery['status'] | '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): RoutingQuery {
  const params: RoutingQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.status) params.status = query.status
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listRoutings(buildQuery())
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
  query.status = ''
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 物料下拉选项
// --------------------------------------------------------------------------- #
const materialOptions = ref<Material[]>([])

async function loadMaterialOptions() {
  try {
    const data = await listMaterials({ page: 1, page_size: 200 })
    materialOptions.value = data.items
  } catch (error) {
    ElMessage.error((error as Error).message)
  }
}

// --------------------------------------------------------------------------- #
// 工艺路线：新增 / 编辑
// --------------------------------------------------------------------------- #
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  code: '',
  material_id: undefined as number | undefined,
  name: '',
  version: 'V1.0',
  is_default: false,
  status: 'DRAFT' as RoutingPayload['status'],
  remark: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入工艺路线编码', trigger: 'blur' }],
  material_id: [{ required: true, message: '请选择适用物料', trigger: 'change' }],
  name: [{ required: true, message: '请输入工艺路线名称', trigger: 'blur' }],
}

function resetForm() {
  form.code = ''
  form.material_id = undefined
  form.name = ''
  form.version = 'V1.0'
  form.is_default = false
  form.status = 'DRAFT'
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Routing) {
  editingId.value = row.id
  form.code = row.code
  form.material_id = row.material_id
  form.name = row.name
  form.version = row.version
  form.is_default = row.is_default
  form.status = row.status
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串与未填写的数字统一转成 null，避免把空值写成字符串 */
function buildPayload(): RoutingPayload {
  return {
    code: form.code,
    material_id: form.material_id as number,
    name: form.name,
    version: form.version || 'V1.0',
    is_default: form.is_default,
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
      await createRouting(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateRouting(editingId.value, buildPayload())
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

async function handleDelete(row: Routing) {
  await ElMessageBox.confirm(`确定删除工艺路线「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteRouting(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 工序：维护弹窗
// --------------------------------------------------------------------------- #
const stepDialogVisible = ref(false)
const stepLoading = ref(false)
const currentRouting = ref<Routing | null>(null)
const steps = ref<RoutingStep[]>([])

function openSteps(row: Routing) {
  currentRouting.value = row
  steps.value = []
  stepDialogVisible.value = true
  loadSteps()
}

async function loadSteps() {
  if (currentRouting.value === null) {
    return
  }
  stepLoading.value = true
  try {
    const detail = await getRoutingDetail(currentRouting.value.id)
    currentRouting.value = detail
    steps.value = detail.steps
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    stepLoading.value = false
  }
}

const stepFormVisible = ref(false)
const stepSubmitting = ref(false)
const editingStepId = ref<number | null>(null)
const stepFormRef = ref<FormInstance>()

const stepForm = reactive({
  step_no: 10,
  step_code: '',
  step_name: '',
  work_center: '',
  equipment: '',
  setup_minutes: undefined as number | undefined,
  run_minutes: undefined as number | undefined,
  is_key: false,
  remark: '',
})

const stepRules: FormRules = {
  step_name: [{ required: true, message: '请输入工序名称', trigger: 'blur' }],
}

function resetStepForm() {
  stepForm.step_no = 10
  stepForm.step_code = ''
  stepForm.step_name = ''
  stepForm.work_center = ''
  stepForm.equipment = ''
  stepForm.setup_minutes = undefined
  stepForm.run_minutes = undefined
  stepForm.is_key = false
  stepForm.remark = ''
}

function openStepCreate() {
  editingStepId.value = null
  resetStepForm()
  stepFormVisible.value = true
}

function openStepEdit(row: RoutingStep) {
  editingStepId.value = row.id
  stepForm.step_no = row.step_no
  stepForm.step_code = row.step_code ?? ''
  stepForm.step_name = row.step_name
  stepForm.work_center = row.work_center ?? ''
  stepForm.equipment = row.equipment ?? ''
  stepForm.setup_minutes = row.setup_minutes ?? undefined
  stepForm.run_minutes = row.run_minutes ?? undefined
  stepForm.is_key = row.is_key
  stepForm.remark = row.remark ?? ''
  stepFormVisible.value = true
}

/** 空串与未填写的数字统一转成 null，避免把空值写成字符串 */
function buildStepPayload(): RoutingStepPayload {
  return {
    step_no: stepForm.step_no,
    step_code: stepForm.step_code || null,
    step_name: stepForm.step_name,
    work_center: stepForm.work_center || null,
    equipment: stepForm.equipment || null,
    setup_minutes: stepForm.setup_minutes ?? null,
    run_minutes: stepForm.run_minutes ?? null,
    is_key: stepForm.is_key,
    remark: stepForm.remark || null,
  }
}

async function handleStepSubmit() {
  if (currentRouting.value === null) {
    return
  }
  const valid = await stepFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  const routingId = currentRouting.value.id
  stepSubmitting.value = true
  try {
    if (editingStepId.value === null) {
      await createRoutingStep(routingId, buildStepPayload())
      ElMessage.success('新增成功')
    } else {
      await updateRoutingStep(routingId, editingStepId.value, buildStepPayload())
      ElMessage.success('修改成功')
    }
    stepFormVisible.value = false
    await loadSteps()
    await load()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    stepSubmitting.value = false
  }
}

async function handleStepDelete(row: RoutingStep) {
  if (currentRouting.value === null) {
    return
  }
  const routingId = currentRouting.value.id
  await ElMessageBox.confirm(`确定删除工序「${row.step_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteRoutingStep(routingId, row.id)
        ElMessage.success('删除成功')
        await loadSteps()
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(() => {
  load()
  loadMaterialOptions()
})
</script>

<template>
  <div>
    <el-form :inline="true" class="panel__query">
      <el-form-item label="关键词">
        <el-input
          v-model="query.keyword"
          placeholder="编码 / 名称 / 版本"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in ROUTING_STATUS_OPTIONS"
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
      <el-button type="primary" @click="openCreate">新增工艺路线</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="工艺路线编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
      <el-table-column label="适用物料" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          <div>{{ row.material_name || '-' }}</div>
          <div class="panel__sub">{{ row.material_code || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="90" />
      <el-table-column label="是否默认" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_default ? 'success' : 'info'">
            {{ row.is_default ? '默认' : '-' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="step_count" label="工序数" width="80" />
      <el-table-column prop="total_minutes" label="单件总工时" width="100" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="ROUTING_STATUS_TAGS[row.status as keyof typeof ROUTING_STATUS_TAGS]">
            {{ ROUTING_STATUS_LABELS[row.status as keyof typeof ROUTING_STATUS_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openSteps(row)">维护工序</el-button>
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
      :title="editingId === null ? '新增工艺路线' : '编辑工艺路线'"
      width="680px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="112px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="工艺路线编码" prop="code">
              <el-input v-model="form.code" placeholder="如 RT-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" placeholder="如 按摩椅装配工艺" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="适用物料" prop="material_id">
              <el-select v-model="form.material_id" filterable placeholder="请选择" style="width: 100%">
                <el-option
                  v-for="item in materialOptions"
                  :key="item.id"
                  :label="`${item.code} ${item.name}`"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="版本">
              <el-input v-model="form.version" placeholder="如 V1.0" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否默认">
              <el-switch v-model="form.is_default" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="item in ROUTING_STATUS_OPTIONS"
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

    <el-dialog v-model="stepDialogVisible" title="维护工序" width="900px">
      <div class="panel__toolbar">
        <el-button type="primary" @click="openStepCreate">新增工序</el-button>
        <span class="panel__count">共 {{ steps.length }} 条</span>
      </div>

      <el-table v-loading="stepLoading" :data="steps" border stripe size="small">
        <el-table-column prop="step_no" label="工序号" width="70" />
        <el-table-column prop="step_code" label="工序编码" width="110" />
        <el-table-column prop="step_name" label="工序名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="work_center" label="工作中心" width="110" />
        <el-table-column prop="equipment" label="设备/工装" min-width="120" show-overflow-tooltip />
        <el-table-column prop="setup_minutes" label="准备工时" width="90" />
        <el-table-column prop="run_minutes" label="单件工时" width="90" />
        <el-table-column label="关键工序" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_key ? 'danger' : 'info'">
              {{ row.is_key ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openStepEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="handleStepDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="stepFormVisible"
      :title="editingStepId === null ? '新增工序' : '编辑工序'"
      width="620px"
    >
      <el-form ref="stepFormRef" :model="stepForm" :rules="stepRules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="工序号">
              <el-input-number v-model="stepForm.step_no" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工序编码">
              <el-input v-model="stepForm.step_code" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工序名称" prop="step_name">
              <el-input v-model="stepForm.step_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作中心">
              <el-input v-model="stepForm.work_center" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备/工装">
              <el-input v-model="stepForm.equipment" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="准备工时">
              <el-input-number
                v-model="stepForm.setup_minutes"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单件工时">
              <el-input-number
                v-model="stepForm.run_minutes"
                :min="0"
                :precision="2"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关键工序">
              <el-switch v-model="stepForm.is_key" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="stepForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="stepFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="stepSubmitting" @click="handleStepSubmit">确定</el-button>
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
