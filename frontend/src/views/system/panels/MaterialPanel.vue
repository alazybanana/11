<script setup lang="ts">
/**
 * 物料主数据维护（产品信息管理）。
 *
 * 标准列表页结构：查询条件 → 工具栏 → 表格 → 分页 → 新增 / 编辑弹窗。
 * 本文件同时作为其它面板的编写范例。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createMaterial,
  deleteMaterial,
  listMaterials,
  updateMaterial,
} from '@/api/system'
import type { Material, MaterialPayload, MaterialQuery } from '@/api/system/types'
import {
  COMMON_STATUS_LABELS,
  COMMON_STATUS_OPTIONS,
  COMMON_STATUS_TAGS,
  MATERIAL_TYPE_LABELS,
  MATERIAL_TYPE_OPTIONS,
  SOURCE_TYPE_LABELS,
  SOURCE_TYPE_OPTIONS,
  SOURCE_TYPE_TAGS,
} from '@/views/system/options'

const loading = ref(false)
const rows = ref<Material[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  material_type: '' as MaterialQuery['material_type'] | '',
  source_type: '' as MaterialQuery['source_type'] | '',
  status: '' as MaterialQuery['status'] | '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): MaterialQuery {
  const params: MaterialQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.material_type) params.material_type = query.material_type
  if (query.source_type) params.source_type = query.source_type
  if (query.status) params.status = query.status
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listMaterials(buildQuery())
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
  query.material_type = ''
  query.source_type = ''
  query.status = ''
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
  spec: '',
  model: '',
  unit: '个',
  category_code: '',
  material_type: 'RAW' as MaterialPayload['material_type'],
  source_type: 'PURCHASE' as MaterialPayload['source_type'],
  standard_cost: undefined as number | undefined,
  safety_stock: undefined as number | undefined,
  lead_time_days: undefined as number | undefined,
  status: 'ENABLED' as MaterialPayload['status'],
  remark: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入物料编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.spec = ''
  form.model = ''
  form.unit = '个'
  form.category_code = ''
  form.material_type = 'RAW'
  form.source_type = 'PURCHASE'
  form.standard_cost = undefined
  form.safety_stock = undefined
  form.lead_time_days = undefined
  form.status = 'ENABLED'
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: Material) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.spec = row.spec ?? ''
  form.model = row.model ?? ''
  form.unit = row.unit
  form.category_code = row.category_code ?? ''
  form.material_type = row.material_type
  form.source_type = row.source_type
  form.standard_cost = row.standard_cost ?? undefined
  form.safety_stock = row.safety_stock ?? undefined
  form.lead_time_days = row.lead_time_days ?? undefined
  form.status = row.status
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串与未填写的数字统一转成 null，避免把空值写成字符串 */
function buildPayload(): MaterialPayload {
  return {
    code: form.code,
    name: form.name,
    spec: form.spec || null,
    model: form.model || null,
    unit: form.unit || '个',
    category_code: form.category_code || null,
    material_type: form.material_type,
    source_type: form.source_type,
    standard_cost: form.standard_cost ?? null,
    safety_stock: form.safety_stock ?? null,
    lead_time_days: form.lead_time_days ?? null,
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
      await createMaterial(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateMaterial(editingId.value, buildPayload())
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

async function handleDelete(row: Material) {
  await ElMessageBox.confirm(`确定删除物料「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteMaterial(row.id)
        ElMessage.success('删除成功')
        await load()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(load)
</script>

<template>
  <div>
    <el-form :inline="true" class="panel__query">
      <el-form-item label="关键词">
        <el-input
          v-model="query.keyword"
          placeholder="编码 / 名称 / 规格 / 型号"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="物料类型">
        <el-select v-model="query.material_type" placeholder="全部" clearable style="width: 130px">
          <el-option
            v-for="item in MATERIAL_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="query.source_type" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in SOURCE_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 110px">
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
      <el-button type="primary" @click="openCreate">新增物料</el-button>
      <span class="panel__count">共 {{ total }} 条</span>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="code" label="物料编码" width="140" />
      <el-table-column prop="name" label="物料名称" min-width="140" />
      <el-table-column prop="model" label="型号" width="110" show-overflow-tooltip />
      <el-table-column prop="spec" label="规格型号" min-width="140" show-overflow-tooltip />
      <el-table-column prop="unit" label="单位" width="70" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">{{ MATERIAL_TYPE_LABELS[row.material_type as keyof typeof MATERIAL_TYPE_LABELS] }}</template>
      </el-table-column>
      <el-table-column label="来源" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="SOURCE_TYPE_TAGS[row.source_type as keyof typeof SOURCE_TYPE_TAGS]">
            {{ SOURCE_TYPE_LABELS[row.source_type as keyof typeof SOURCE_TYPE_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="standard_cost" label="标准成本" width="100" />
      <el-table-column prop="lead_time_days" label="提前期(天)" width="100" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="COMMON_STATUS_TAGS[row.status as keyof typeof COMMON_STATUS_TAGS]">
            {{ COMMON_STATUS_LABELS[row.status as keyof typeof COMMON_STATUS_LABELS] }}
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
      :title="editingId === null ? '新增物料' : '编辑物料'"
      width="620px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="物料编码" prop="code">
              <el-input v-model="form.code" placeholder="如 M-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料名称" prop="name">
              <el-input v-model="form.name" placeholder="如 坐垫海绵" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格型号">
              <el-input v-model="form.spec" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号">
              <el-input v-model="form.model" placeholder="成品 / 半成品常用" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="计量单位">
              <el-input v-model="form.unit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料分类">
              <el-input v-model="form.category_code" placeholder="字典项编码，可空" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="物料类型">
              <el-select v-model="form.material_type" style="width: 100%">
                <el-option
                  v-for="item in MATERIAL_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="来源">
              <el-select v-model="form.source_type" style="width: 100%">
                <el-option
                  v-for="item in SOURCE_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option
                  v-for="item in COMMON_STATUS_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标准成本">
              <el-input-number v-model="form.standard_cost" :min="0" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="安全库存">
              <el-input-number v-model="form.safety_stock" :min="0" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="提前期(天)">
              <el-input-number v-model="form.lead_time_days" :min="0" style="width: 100%" />
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
