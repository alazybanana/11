<script setup lang="ts">
/**
 * 权限资源树管理（系统访问权限管理）。
 *
 * 左右两栏布局：左栏权限资源树，右栏选中权限的详情与操作，
 * 新增 / 编辑统一走底部弹窗表单。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules, TreeInstance } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

import {
  createPermission,
  deletePermission,
  getPermissionTree,
  updatePermission,
} from '@/api/system'
import type { PermissionPayload, PermissionTree } from '@/api/system/types'
import {
  COMMON_STATUS_LABELS,
  COMMON_STATUS_TAGS,
  PERMISSION_TYPE_LABELS,
  PERMISSION_TYPE_OPTIONS,
  PERMISSION_TYPE_TAGS,
} from '@/views/system/options'

/** HTTP 方法候选（可留空表示与接口方法无关的菜单 / 按钮权限） */
const METHOD_OPTIONS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

const treeLoading = ref(false)
const treeData = ref<PermissionTree[]>([])
const current = ref<PermissionTree | null>(null)
const treeRef = ref<TreeInstance>()

/** 在整棵树里按 id 查找节点（刷新后重新定位当前选中项） */
function findNode(nodes: PermissionTree[], id: number): PermissionTree | null {
  for (const node of nodes) {
    if (node.id === id) {
      return node
    }
    const found = findNode(node.children ?? [], id)
    if (found !== null) {
      return found
    }
  }
  return null
}

async function loadTree() {
  treeLoading.value = true
  try {
    treeData.value = await getPermissionTree()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    treeLoading.value = false
  }
}

/** 选中节点并同步树上的高亮 */
async function selectNode(id: number) {
  current.value = findNode(treeData.value, id)
  await nextTick()
  treeRef.value?.setCurrentKey(id)
}

function handleNodeClick(data: PermissionTree) {
  current.value = data
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
  perm_type: 'MENU' as PermissionPayload['perm_type'],
  parent_id: null as number | null,
  path: '',
  method: '',
  sort_order: 0,
  is_enabled: true,
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入权限编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入权限名称', trigger: 'blur' }],
}

/** 上级权限候选：编辑时剔除「自己及其子树」，避免把节点挂到自己下面 */
const parentOptions = computed<PermissionTree[]>(() => {
  if (editingId.value === null) {
    return treeData.value
  }
  return removeSubtree(treeData.value, editingId.value)
})

function removeSubtree(nodes: PermissionTree[], id: number): PermissionTree[] {
  return nodes
    .filter((node) => node.id !== id)
    .map((node) => ({ ...node, children: removeSubtree(node.children ?? [], id) }))
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.perm_type = 'MENU'
  form.parent_id = null
  form.path = ''
  form.method = ''
  form.sort_order = 0
  form.is_enabled = true
}

function openCreateRoot() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openCreateChild() {
  if (current.value === null) {
    return
  }
  editingId.value = null
  resetForm()
  form.parent_id = current.value.id
  dialogVisible.value = true
}

function openEdit() {
  if (current.value === null) {
    return
  }
  editingId.value = current.value.id
  form.code = current.value.code
  form.name = current.value.name
  form.perm_type = current.value.perm_type
  form.parent_id = current.value.parent_id ?? null
  form.path = current.value.path ?? ''
  form.method = current.value.method ?? ''
  form.sort_order = current.value.sort_order
  form.is_enabled = current.value.is_enabled
  dialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildPayload(): PermissionPayload {
  return {
    code: form.code,
    name: form.name,
    perm_type: form.perm_type,
    parent_id: form.parent_id ?? null,
    path: form.path || null,
    method: form.method || null,
    sort_order: form.sort_order,
    is_enabled: form.is_enabled,
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  submitting.value = true
  try {
    let savedId: number
    if (editingId.value === null) {
      const created = await createPermission(buildPayload())
      savedId = created.id
      ElMessage.success('新增成功')
    } else {
      await updatePermission(editingId.value, buildPayload())
      savedId = editingId.value
      ElMessage.success('修改成功')
    }
    dialogVisible.value = false
    await loadTree()
    await selectNode(savedId)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete() {
  const node = current.value
  if (node === null) {
    return
  }

  await ElMessageBox.confirm(`确定删除权限「${node.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deletePermission(node.id)
        ElMessage.success('删除成功')
        current.value = null
        await loadTree()
      } catch (error) {
        ElMessage.error((error as Error).message)
      }
    })
    .catch(() => undefined)
}

onMounted(loadTree)
</script>

<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="10">
        <div class="panel__toolbar">
          <el-button type="primary" @click="openCreateRoot">新增根权限</el-button>
          <span class="panel__count">共 {{ treeData.length }} 个根节点</span>
        </div>
        <div v-loading="treeLoading" class="panel__tree">
          <el-tree
            ref="treeRef"
            :data="treeData"
            node-key="id"
            default-expand-all
            highlight-current
            :props="{ label: 'name', children: 'children' }"
            @node-click="handleNodeClick"
          >
            <template #default="{ data }">
              <span class="panel__node">
                <span>{{ data.name }}</span>
                <span class="panel__node-code">{{ data.code }}</span>
                <el-tag
                  size="small"
                  :type="PERMISSION_TYPE_TAGS[data.perm_type as keyof typeof PERMISSION_TYPE_TAGS]"
                >
                  {{
                    PERMISSION_TYPE_LABELS[data.perm_type as keyof typeof PERMISSION_TYPE_LABELS]
                  }}
                </el-tag>
              </span>
            </template>
          </el-tree>
        </div>
      </el-col>

      <el-col :span="14">
        <template v-if="current !== null">
          <el-descriptions :column="1" border size="small" title="权限详情">
            <el-descriptions-item label="权限编码">{{ current.code }}</el-descriptions-item>
            <el-descriptions-item label="权限名称">{{ current.name }}</el-descriptions-item>
            <el-descriptions-item label="权限类型">
              <el-tag
                size="small"
                :type="
                  PERMISSION_TYPE_TAGS[current.perm_type as keyof typeof PERMISSION_TYPE_TAGS]
                "
              >
                {{
                  PERMISSION_TYPE_LABELS[current.perm_type as keyof typeof PERMISSION_TYPE_LABELS]
                }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上级权限 ID">
              {{ current.parent_id ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="路由 / 接口路径">{{ current.path ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="HTTP 方法">{{ current.method ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="排序">{{ current.sort_order }}</el-descriptions-item>
            <el-descriptions-item label="是否启用">
              <el-tag
                size="small"
                :type="COMMON_STATUS_TAGS[current.is_enabled ? 'ENABLED' : 'DISABLED']"
              >
                {{ COMMON_STATUS_LABELS[current.is_enabled ? 'ENABLED' : 'DISABLED'] }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>

          <div class="panel__toolbar panel__actions">
            <el-button type="primary" @click="openCreateChild">新增下级</el-button>
            <el-button @click="openEdit">编辑</el-button>
            <el-button type="danger" @click="handleDelete">删除</el-button>
          </div>
        </template>

        <el-empty v-else description="请在左侧选择权限资源" />
      </el-col>
    </el-row>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新增权限' : '编辑权限'"
      width="620px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="权限编码" prop="code">
              <el-input v-model="form.code" placeholder="如 system:material:list" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="权限名称" prop="name">
              <el-input v-model="form.name" placeholder="如 物料查询" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="权限类型">
              <el-select v-model="form.perm_type" style="width: 100%">
                <el-option
                  v-for="item in PERMISSION_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="上级权限">
              <el-tree-select
                v-model="form.parent_id"
                :data="parentOptions"
                node-key="id"
                :props="{ label: 'name', children: 'children' }"
                check-strictly
                clearable
                placeholder="不选表示根权限"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="路由 / 接口路径">
              <el-input v-model="form.path" placeholder="如 /system/materials" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="HTTP 方法">
              <el-select v-model="form.method" placeholder="可空" clearable style="width: 100%">
                <el-option v-for="item in METHOD_OPTIONS" :key="item" :label="item" :value="item" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否启用">
              <el-switch v-model="form.is_enabled" />
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

.panel__tree {
  min-height: 320px;
  max-height: 62vh;
  overflow: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 8px;
}

.panel__node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel__node-code {
  font-size: 12px;
  color: #909399;
}

.panel__actions {
  margin-top: 12px;
}
</style>
