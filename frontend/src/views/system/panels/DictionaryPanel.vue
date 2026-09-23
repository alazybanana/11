<script setup lang="ts">
/**
 * 共性基础字典维护（字典类型 + 字典项）。
 *
 * 采用左右两栏：左栏维护字典类型并选中一行，右栏维护该类型下的字典项。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import {
  createDictionaryItem,
  createDictionaryType,
  deleteDictionaryItem,
  deleteDictionaryType,
  listDictionaryItems,
  listDictionaryTypes,
  updateDictionaryItem,
  updateDictionaryType,
} from '@/api/system'
import type {
  DictionaryItem,
  DictionaryItemPayload,
  DictionaryItemQuery,
  DictionaryType,
  DictionaryTypePayload,
  DictionaryTypeQuery,
} from '@/api/system/types'

// --------------------------------------------------------------------------- #
// 左栏：字典类型
// --------------------------------------------------------------------------- #
const typeLoading = ref(false)
const typeRows = ref<DictionaryType[]>([])
const typeTotal = ref(0)
const selectedType = ref<DictionaryType | null>(null)

const typeQuery = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
})

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildTypeQuery(): DictionaryTypeQuery {
  const params: DictionaryTypeQuery = { page: typeQuery.page, page_size: typeQuery.page_size }
  if (typeQuery.keyword) params.keyword = typeQuery.keyword
  return params
}

async function loadTypes() {
  typeLoading.value = true
  try {
    const data = await listDictionaryTypes(buildTypeQuery())
    typeRows.value = data.items
    typeTotal.value = data.total
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    typeLoading.value = false
  }
}

function handleTypeSearch() {
  typeQuery.page = 1
  loadTypes()
}

function handleTypeReset() {
  typeQuery.keyword = ''
  handleTypeSearch()
}

// --------------------------------------------------------------------------- #
// 右栏：字典项
// --------------------------------------------------------------------------- #
const itemLoading = ref(false)
const itemRows = ref<DictionaryItem[]>([])
const itemTotal = ref(0)

const itemQuery = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
})

function buildItemQuery(): DictionaryItemQuery {
  const params: DictionaryItemQuery = { page: itemQuery.page, page_size: itemQuery.page_size }
  if (itemQuery.keyword) params.keyword = itemQuery.keyword
  if (selectedType.value !== null) params.type_id = selectedType.value.id
  return params
}

async function loadItems() {
  if (selectedType.value === null) {
    itemRows.value = []
    itemTotal.value = 0
    return
  }

  itemLoading.value = true
  try {
    const data = await listDictionaryItems(buildItemQuery())
    itemRows.value = data.items
    itemTotal.value = data.total
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    itemLoading.value = false
  }
}

/** 切换字典类型：类型变了就回到第一页并清空关键词后重新查询字典项 */
function handleTypeChange(row: DictionaryType | null) {
  const changed = (selectedType.value?.id ?? null) !== (row?.id ?? null)
  selectedType.value = row
  if (!changed) {
    return
  }
  itemQuery.page = 1
  itemQuery.keyword = ''
  loadItems()
}

function handleItemSearch() {
  itemQuery.page = 1
  loadItems()
}

function handleItemReset() {
  itemQuery.keyword = ''
  handleItemSearch()
}

// --------------------------------------------------------------------------- #
// 字典类型新增 / 编辑
// --------------------------------------------------------------------------- #
const typeDialogVisible = ref(false)
const typeSubmitting = ref(false)
const editingTypeId = ref<number | null>(null)
const typeFormRef = ref<FormInstance>()

const typeForm = reactive({
  code: '',
  name: '',
  is_enabled: true,
  remark: '',
})

const typeRules: FormRules = {
  code: [{ required: true, message: '请输入字典类型编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入字典类型名称', trigger: 'blur' }],
}

function resetTypeForm() {
  typeForm.code = ''
  typeForm.name = ''
  typeForm.is_enabled = true
  typeForm.remark = ''
}

function openTypeCreate() {
  editingTypeId.value = null
  resetTypeForm()
  typeDialogVisible.value = true
}

function openTypeEdit(row: DictionaryType) {
  editingTypeId.value = row.id
  typeForm.code = row.code
  typeForm.name = row.name
  typeForm.is_enabled = row.is_enabled
  typeForm.remark = row.remark ?? ''
  typeDialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildTypePayload(): DictionaryTypePayload {
  return {
    code: typeForm.code,
    name: typeForm.name,
    is_enabled: typeForm.is_enabled,
    remark: typeForm.remark || null,
  }
}

async function handleTypeSubmit() {
  const valid = await typeFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  typeSubmitting.value = true
  try {
    if (editingTypeId.value === null) {
      await createDictionaryType(buildTypePayload())
      ElMessage.success('新增成功')
    } else {
      await updateDictionaryType(editingTypeId.value, buildTypePayload())
      ElMessage.success('修改成功')
    }
    typeDialogVisible.value = false
    await loadTypes()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    typeSubmitting.value = false
  }
}

/** 系统内置字典后端会拒绝删除，这里直接把按钮禁用 */
async function handleTypeDelete(row: DictionaryType) {
  await ElMessageBox.confirm(`确定删除字典类型「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteDictionaryType(row.id)
        ElMessage.success('删除成功')
        if (selectedType.value?.id === row.id) {
          selectedType.value = null
          itemRows.value = []
          itemTotal.value = 0
        }
        await loadTypes()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

// --------------------------------------------------------------------------- #
// 字典项新增 / 编辑
// --------------------------------------------------------------------------- #
const itemDialogVisible = ref(false)
const itemSubmitting = ref(false)
const editingItemId = ref<number | null>(null)
const itemFormRef = ref<FormInstance>()

const itemForm = reactive({
  item_code: '',
  item_label: '',
  item_value: '',
  sort_order: 0,
  is_enabled: true,
  remark: '',
})

const itemRules: FormRules = {
  item_code: [{ required: true, message: '请输入字典项编码', trigger: 'blur' }],
  item_label: [{ required: true, message: '请输入字典项显示名', trigger: 'blur' }],
}

function resetItemForm() {
  itemForm.item_code = ''
  itemForm.item_label = ''
  itemForm.item_value = ''
  itemForm.sort_order = 0
  itemForm.is_enabled = true
  itemForm.remark = ''
}

function openItemCreate() {
  if (selectedType.value === null) {
    return
  }
  editingItemId.value = null
  resetItemForm()
  itemDialogVisible.value = true
}

function openItemEdit(row: DictionaryItem) {
  editingItemId.value = row.id
  itemForm.item_code = row.item_code
  itemForm.item_label = row.item_label
  itemForm.item_value = row.item_value ?? ''
  itemForm.sort_order = row.sort_order
  itemForm.is_enabled = row.is_enabled
  itemForm.remark = row.remark ?? ''
  itemDialogVisible.value = true
}

function buildItemPayload(): DictionaryItemPayload {
  return {
    item_code: itemForm.item_code,
    item_label: itemForm.item_label,
    item_value: itemForm.item_value || null,
    sort_order: itemForm.sort_order,
    is_enabled: itemForm.is_enabled,
    remark: itemForm.remark || null,
  }
}

async function handleItemSubmit() {
  const type = selectedType.value
  if (type === null) {
    return
  }

  const valid = await itemFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  itemSubmitting.value = true
  try {
    if (editingItemId.value === null) {
      await createDictionaryItem(type.id, buildItemPayload())
      ElMessage.success('新增成功')
    } else {
      await updateDictionaryItem(editingItemId.value, buildItemPayload())
      ElMessage.success('修改成功')
    }
    itemDialogVisible.value = false
    await loadItems()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    itemSubmitting.value = false
  }
}

async function handleItemDelete(row: DictionaryItem) {
  await ElMessageBox.confirm(`确定删除字典项「${row.item_label}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteDictionaryItem(row.id)
        ElMessage.success('删除成功')
        await loadItems()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(loadTypes)
</script>

<template>
  <el-row :gutter="12">
    <el-col :span="10">
      <el-form :inline="true" class="panel__query">
        <el-form-item label="关键词">
          <el-input
            v-model="typeQuery.keyword"
            placeholder="编码 / 名称"
            clearable
            style="width: 160px"
            @keyup.enter="handleTypeSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleTypeSearch">查询</el-button>
          <el-button @click="handleTypeReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div class="panel__toolbar">
        <el-button type="primary" @click="openTypeCreate">新增字典类型</el-button>
        <span class="panel__count">共 {{ typeTotal }} 条</span>
      </div>

      <el-table
        v-loading="typeLoading"
        highlight-current-row
        row-key="id"
        :data="typeRows"
        border
        stripe
        size="small"
        @current-change="handleTypeChange"
      >
        <el-table-column prop="code" label="字典类型编码" min-width="110" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
        <el-table-column label="内置" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" size="small" type="warning">系统内置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_enabled ? 'success' : 'info'">
              {{ row.is_enabled ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTypeEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.is_system" @click="handleTypeDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="panel__pagination"
        background
        layout="total, sizes, prev, pager, next"
        :total="typeTotal"
        v-model:current-page="typeQuery.page"
        v-model:page-size="typeQuery.page_size"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="loadTypes"
        @size-change="handleTypeSearch"
      />
    </el-col>

    <el-col :span="14">
      <div class="panel__toolbar">
        <span class="dict-items__title">字典项 —— {{ selectedType === null ? '未选择' : selectedType.name }}</span>
        <el-button type="primary" :disabled="selectedType === null" @click="openItemCreate">
          新增字典项
        </el-button>
        <span class="panel__count">共 {{ itemTotal }} 条</span>
      </div>

      <el-empty v-if="selectedType === null" description="请先在左侧选择字典类型" />
      <template v-else>
        <el-form :inline="true" class="panel__query">
          <el-form-item label="关键词">
            <el-input
              v-model="itemQuery.keyword"
              placeholder="编码 / 显示名"
              clearable
              style="width: 160px"
              @keyup.enter="handleItemSearch"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleItemSearch">查询</el-button>
            <el-button @click="handleItemReset">重置</el-button>
          </el-form-item>
        </el-form>

        <el-table v-loading="itemLoading" :data="itemRows" border stripe size="small">
          <el-table-column prop="item_code" label="字典项编码" min-width="110" show-overflow-tooltip />
          <el-table-column prop="item_label" label="显示名" min-width="110" show-overflow-tooltip />
          <el-table-column prop="item_value" label="字典值" min-width="100" show-overflow-tooltip />
          <el-table-column prop="sort_order" label="排序" width="70" />
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_enabled ? 'success' : 'info'">
                {{ row.is_enabled ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="110" show-overflow-tooltip />
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openItemEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleItemDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="panel__pagination"
          background
          layout="total, sizes, prev, pager, next"
          :total="itemTotal"
          v-model:current-page="itemQuery.page"
          v-model:page-size="itemQuery.page_size"
          :page-sizes="[10, 20, 50, 100]"
          @current-change="loadItems"
          @size-change="handleItemSearch"
        />
      </template>
    </el-col>
  </el-row>

  <el-dialog
    v-model="typeDialogVisible"
    :title="editingTypeId === null ? '新增字典类型' : '编辑字典类型'"
    width="560px"
  >
    <el-form ref="typeFormRef" :model="typeForm" :rules="typeRules" label-width="96px">
      <el-form-item label="类型编码" prop="code">
        <el-input v-model="typeForm.code" placeholder="如 MATERIAL_TYPE" />
      </el-form-item>
      <el-form-item label="类型名称" prop="name">
        <el-input v-model="typeForm.name" placeholder="如 物料类型" />
      </el-form-item>
      <el-form-item label="是否启用">
        <el-switch v-model="typeForm.is_enabled" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="typeForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="typeDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="typeSubmitting" @click="handleTypeSubmit">确定</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="itemDialogVisible"
    :title="editingItemId === null ? '新增字典项' : '编辑字典项'"
    width="560px"
  >
    <el-form ref="itemFormRef" :model="itemForm" :rules="itemRules" label-width="96px">
      <el-form-item label="字典项编码" prop="item_code">
        <el-input v-model="itemForm.item_code" placeholder="如 RAW" />
      </el-form-item>
      <el-form-item label="显示名" prop="item_label">
        <el-input v-model="itemForm.item_label" placeholder="如 原材料" />
      </el-form-item>
      <el-form-item label="字典值">
        <el-input v-model="itemForm.item_value" placeholder="可空，默认与编码相同" />
      </el-form-item>
      <el-form-item label="排序">
        <el-input-number v-model="itemForm.sort_order" :min="0" style="width: 100%" />
      </el-form-item>
      <el-form-item label="是否启用">
        <el-switch v-model="itemForm.is_enabled" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="itemForm.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="itemDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="itemSubmitting" @click="handleItemSubmit">确定</el-button>
    </template>
  </el-dialog>
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

.dict-items__title {
  font-size: 14px;
  font-weight: 600;
}
</style>
