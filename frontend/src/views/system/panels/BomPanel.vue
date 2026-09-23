<script setup lang="ts">
/**
 * BOM 建立与维护（BOM 头 + BOM 行）。
 *
 * 列表页维护 BOM 头；「维护BOM行」弹窗内维护子件明细。
 * 已发布（RELEASED）的 BOM 不允许增删改行，需先置为草稿。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import {
  createBom,
  createBomLine,
  deleteBom,
  deleteBomLine,
  getBomDetail,
  getBomTree,
  listBoms,
  listMaterials,
  updateBom,
  updateBomLine,
} from '@/api/system'
import type {
  Bom,
  BomLine,
  BomLinePayload,
  BomPayload,
  BomQuery,
  BomTreeNode,
  Material,
} from '@/api/system/types'
import {
  BOM_STATUS_LABELS,
  BOM_STATUS_OPTIONS,
  BOM_STATUS_TAGS,
} from '@/views/system/options'

/** BOM 类型（DESIGN 设计 / MANUFACTURE 制造 / SALE 销售） */
const BOM_TYPE_OPTIONS = [
  { label: '制造 BOM', value: 'MANUFACTURE' },
  { label: '设计 BOM', value: 'DESIGN' },
  { label: '销售 BOM', value: 'SALE' },
] as const

const BOM_TYPE_LABELS: Record<string, string> = {
  DESIGN: '设计',
  MANUFACTURE: '制造',
  SALE: '销售',
}

const BOM_TYPE_TAGS: Record<string, 'primary' | 'success' | 'warning'> = {
  DESIGN: 'warning',
  MANUFACTURE: 'primary',
  SALE: 'success',
}

const loading = ref(false)
const rows = ref<Bom[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  status: '' as BomQuery['status'] | '',
  bom_type: '' as BomQuery['bom_type'] | '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): BomQuery {
  const params: BomQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.status) params.status = query.status
  if (query.bom_type) params.bom_type = query.bom_type
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listBoms(buildQuery())
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
  query.bom_type = ''
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 物料下拉选项（父件 / 子件共用）
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
// BOM 头：新增 / 编辑
// --------------------------------------------------------------------------- #
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  code: '',
  parent_material_id: undefined as number | undefined,
  bom_type: 'MANUFACTURE' as BomPayload['bom_type'],
  version: 'V1.0',
  base_qty: 1,
  status: 'DRAFT' as BomPayload['status'],
  effective_from: '',
  effective_to: '',
  remark: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入 BOM 编码', trigger: 'blur' }],
  parent_material_id: [{ required: true, message: '请选择父件物料', trigger: 'change' }],
  bom_type: [{ required: true, message: '请选择 BOM 类型', trigger: 'change' }],
}

function resetForm() {
  form.code = ''
  form.parent_material_id = undefined
  form.bom_type = 'MANUFACTURE'
  form.version = 'V1.0'
  form.base_qty = 1
  form.status = 'DRAFT'
  form.effective_from = ''
  form.effective_to = ''
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Bom) {
  editingId.value = row.id
  form.code = row.code
  form.parent_material_id = row.parent_material_id
  form.bom_type = row.bom_type
  form.version = row.version
  form.base_qty = row.base_qty
  form.status = row.status
  form.effective_from = row.effective_from ?? ''
  form.effective_to = row.effective_to ?? ''
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串与未填写的数字统一转成 null，避免把空值写成字符串 */
function buildPayload(): BomPayload {
  return {
    code: form.code,
    parent_material_id: form.parent_material_id as number,
    bom_type: form.bom_type,
    version: form.version || 'V1.0',
    base_qty: form.base_qty,
    status: form.status,
    effective_from: form.effective_from || null,
    effective_to: form.effective_to || null,
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
      await createBom(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateBom(editingId.value, buildPayload())
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

async function handleDelete(row: Bom) {
  await ElMessageBox.confirm(`确定删除 BOM「${row.code}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteBom(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// BOM 行：维护弹窗
// --------------------------------------------------------------------------- #
const lineDialogVisible = ref(false)
const lineLoading = ref(false)
const currentBom = ref<Bom | null>(null)
const lines = ref<BomLine[]>([])

/** 已发布的 BOM 不允许修改行 */
const linesLocked = computed(() => currentBom.value?.status === 'RELEASED')

function openLines(row: Bom) {
  currentBom.value = row
  lines.value = []
  lineDialogVisible.value = true
  loadLines()
}

async function loadLines() {
  if (currentBom.value === null) {
    return
  }
  lineLoading.value = true
  try {
    const detail = await getBomDetail(currentBom.value.id)
    currentBom.value = detail
    lines.value = detail.lines
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    lineLoading.value = false
  }
}

const lineDialogFormVisible = ref(false)
const lineSubmitting = ref(false)
const editingLineId = ref<number | null>(null)
const lineFormRef = ref<FormInstance>()

const lineForm = reactive({
  line_no: 10,
  child_material_id: undefined as number | undefined,
  quantity: 1,
  unit: '',
  loss_rate: 0,
  position: '',
  is_phantom: false,
  remark: '',
})

const lineRules: FormRules = {
  child_material_id: [{ required: true, message: '请选择子件物料', trigger: 'change' }],
}

function resetLineForm() {
  lineForm.line_no = 10
  lineForm.child_material_id = undefined
  lineForm.quantity = 1
  lineForm.unit = ''
  lineForm.loss_rate = 0
  lineForm.position = ''
  lineForm.is_phantom = false
  lineForm.remark = ''
}

function openLineCreate() {
  if (linesLocked.value) {
    return
  }
  editingLineId.value = null
  resetLineForm()
  lineDialogFormVisible.value = true
}

function openLineEdit(row: BomLine) {
  if (linesLocked.value) {
    return
  }
  editingLineId.value = row.id
  lineForm.line_no = row.line_no
  lineForm.child_material_id = row.child_material_id
  lineForm.quantity = row.quantity
  lineForm.unit = row.unit ?? ''
  lineForm.loss_rate = row.loss_rate
  lineForm.position = row.position ?? ''
  lineForm.is_phantom = row.is_phantom
  lineForm.remark = row.remark ?? ''
  lineDialogFormVisible.value = true
}

/** 空串与未填写的数字统一转成 null，避免把空值写成字符串 */
function buildLinePayload(): BomLinePayload {
  return {
    line_no: lineForm.line_no,
    child_material_id: lineForm.child_material_id as number,
    quantity: lineForm.quantity,
    unit: lineForm.unit || null,
    loss_rate: lineForm.loss_rate,
    position: lineForm.position || null,
    is_phantom: lineForm.is_phantom,
    remark: lineForm.remark || null,
  }
}

async function handleLineSubmit() {
  if (currentBom.value === null) {
    return
  }
  const valid = await lineFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  const bomId = currentBom.value.id
  lineSubmitting.value = true
  try {
    if (editingLineId.value === null) {
      await createBomLine(bomId, buildLinePayload())
      ElMessage.success('新增成功')
    } else {
      await updateBomLine(bomId, editingLineId.value, buildLinePayload())
      ElMessage.success('修改成功')
    }
    lineDialogFormVisible.value = false
    await loadLines()
    await load()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    lineSubmitting.value = false
  }
}

async function handleLineDelete(row: BomLine) {
  if (currentBom.value === null) {
    return
  }
  const bomId = currentBom.value.id
  await ElMessageBox.confirm(`确定删除第 ${row.line_no} 行吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteBomLine(bomId, row.id)
        ElMessage.success('删除成功')
        await loadLines()
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 多层 BOM 展开（树查看）
// --------------------------------------------------------------------------- #
const treeVisible = ref(false)
const treeLoading = ref(false)
const treeData = ref<BomTreeNode[]>([])
const treeTitle = ref('')

function openTree(row: Bom) {
  treeTitle.value = `${row.code}（父件：${row.parent_material_code ?? ''}）`
  treeData.value = []
  treeVisible.value = true
  loadTree(row)
}

async function loadTree(row: Bom) {
  treeLoading.value = true
  try {
    treeData.value = [await getBomTree(row.parent_material_id)]
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    treeLoading.value = false
  }
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
          placeholder="BOM 编码 / 版本"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.bom_type" placeholder="全部" clearable style="width: 120px">
          <el-option
            v-for="item in BOM_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in BOM_STATUS_OPTIONS"
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
      <el-button type="primary" @click="openCreate">新增 BOM</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="BOM 编码" width="140" />
      <el-table-column label="父件物料" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <div>{{ row.parent_material_name || '-' }}</div>
          <div class="panel__sub">{{ row.parent_material_code || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="BOM_TYPE_TAGS[row.bom_type as keyof typeof BOM_TYPE_TAGS] ?? 'info'">
            {{ BOM_TYPE_LABELS[row.bom_type] ?? row.bom_type }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="90" />
      <el-table-column prop="base_qty" label="基准数量" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="BOM_STATUS_TAGS[row.status as keyof typeof BOM_STATUS_TAGS]">
            {{ BOM_STATUS_LABELS[row.status as keyof typeof BOM_STATUS_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="line_count" label="行数" width="70" />
      <el-table-column label="操作" width="270" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openLines(row)">维护BOM行</el-button>
          <el-button link type="success" @click="openTree(row)">查看多层树</el-button>
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
      :title="editingId === null ? '新增 BOM' : '编辑 BOM'"
      width="680px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="BOM 编码" prop="code">
              <el-input v-model="form.code" placeholder="如 BOM-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="父件物料" prop="parent_material_id">
              <el-select v-model="form.parent_material_id" filterable placeholder="请选择" style="width: 100%">
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
            <el-form-item label="BOM 类型" prop="bom_type">
              <el-select v-model="form.bom_type" style="width: 100%">
                <el-option
                  v-for="item in BOM_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
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
            <el-form-item label="基准数量">
              <el-input-number v-model="form.base_qty" :min="0.0001" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="item in BOM_STATUS_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="生效日期">
              <el-date-picker
                v-model="form.effective_from"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="可空"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="失效日期">
              <el-date-picker
                v-model="form.effective_to"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="可空"
                style="width: 100%"
              />
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

    <el-dialog v-model="lineDialogVisible" title="维护 BOM 行" width="900px">
      <el-alert
        v-if="linesLocked"
        type="info"
        :closable="false"
        show-icon
        title="已发布的 BOM 不允许修改行，请先置为草稿"
        style="margin-bottom: 12px"
      />

      <div class="panel__toolbar">
        <el-button type="primary" :disabled="linesLocked" @click="openLineCreate">新增行</el-button>
        <span class="panel__count">共 {{ lines.length }} 条</span>
      </div>

      <el-table v-loading="lineLoading" :data="lines" border stripe size="small">
        <el-table-column prop="line_no" label="行号" width="70" />
        <el-table-column label="子件物料" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.material_code }} {{ row.material_name }}
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="单位用量" width="100" />
        <el-table-column prop="unit" label="单位" width="70" />
        <el-table-column prop="loss_rate" label="损耗率" width="90" />
        <el-table-column prop="position" label="装配位置" min-width="120" show-overflow-tooltip />
        <el-table-column label="虚拟件" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_phantom ? 'danger' : 'info'">
              {{ row.is_phantom ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="linesLocked" @click="openLineEdit(row)">
              编辑
            </el-button>
            <el-button link type="danger" :disabled="linesLocked" @click="handleLineDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="lineDialogFormVisible"
      :title="editingLineId === null ? '新增 BOM 行' : '编辑 BOM 行'"
      width="620px"
    >
      <el-form ref="lineFormRef" :model="lineForm" :rules="lineRules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="行号">
              <el-input-number v-model="lineForm.line_no" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="子件物料" prop="child_material_id">
              <el-select
                v-model="lineForm.child_material_id"
                filterable
                placeholder="请选择"
                style="width: 100%"
              >
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
            <el-form-item label="单位用量">
              <el-input-number
                v-model="lineForm.quantity"
                :min="0.0001"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计量单位">
              <el-input v-model="lineForm.unit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="损耗率">
              <el-input-number
                v-model="lineForm.loss_rate"
                :min="0"
                :max="1"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="装配位置">
              <el-input v-model="lineForm.position" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="虚拟件">
              <el-switch v-model="lineForm.is_phantom" />
              <div class="panel__sub">虚拟件不实际入库，展开时直接穿透到下层子件</div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="lineForm.remark" type="textarea" :rows="2" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="lineDialogFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="lineSubmitting" @click="handleLineSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="treeVisible" :title="`多层 BOM 展开：${treeTitle}`" width="720px">
      <el-tree
        v-loading="treeLoading"
        :data="treeData"
        node-key="material_id"
        default-expand-all
        :expand-on-click-node="false"
      >
        <template #default="{ data }">
          <span>
            <span class="tree__qty">{{ data.material_code }} {{ data.material_name }}</span>
            <el-tag v-if="data.is_phantom" size="small" type="danger" style="margin-left: 8px">
              虚拟件
            </el-tag>
            <span class="tree__qty panel__sub">
              累计用量 ×{{ data.acc_quantity }} {{ data.unit }}
            </span>
          </span>
        </template>
      </el-tree>
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

.panel__sub {
  font-size: 12px;
  color: #909399;
}

.tree__qty {
  margin-left: 8px;
}
</style>
