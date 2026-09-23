<script setup lang="ts">
/**
 * 组织结构树维护（组织与人员信息管理）。
 *
 * 与其它面板的列表页结构不同，这里采用左右两栏：
 * 左栏是组织结构树（关键词在前端过滤整棵树），右栏是选中组织的详情与操作。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules, TreeInstance } from 'element-plus'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'

import {
  createOrganization,
  deleteOrganization,
  getOrganizationTree,
  updateOrganization,
} from '@/api/system'
import type { OrganizationPayload, OrganizationTree } from '@/api/system/types'
import { ORG_TYPE_LABELS, ORG_TYPE_OPTIONS, ORG_TYPE_TAGS } from '@/views/system/options'

const loading = ref(false)
const treeData = ref<OrganizationTree[]>([])
const keyword = ref('')
const treeRef = ref<TreeInstance>()
const selected = ref<OrganizationTree | null>(null)

/** 递归统计组织节点总数，用于左栏的统计展示 */
function countNodes(nodes: OrganizationTree[]): number {
  let total = 0
  for (const node of nodes) {
    total += 1 + countNodes(node.children)
  }
  return total
}

const nodeCount = computed(() => countNodes(treeData.value))

/** 在整棵树里按 id 定位节点，用于重新加载后恢复选中项 */
function findNode(nodes: OrganizationTree[], id: number): OrganizationTree | null {
  for (const node of nodes) {
    if (node.id === id) {
      return node
    }
    const matched = findNode(node.children, id)
    if (matched !== null) {
      return matched
    }
  }
  return null
}

/** 关键词匹配编码 / 名称 / 负责人，空串表示不过滤 */
function filterNode(value: string, data: OrganizationTree): boolean {
  const target = value.trim().toLowerCase()
  if (!target) {
    return true
  }
  const fields = [data.code, data.name, data.leader ?? '']
  return fields.some((field) => field.toLowerCase().includes(target))
}

watch(keyword, (value) => {
  treeRef.value?.filter(value)
})

async function load() {
  loading.value = true
  try {
    treeData.value = await getOrganizationTree()
    // 选中的组织可能已被删除，找不到就清空右栏
    const current = selected.value
    selected.value = current === null ? null : findNode(treeData.value, current.id)
    await nextTick()
    treeRef.value?.setCurrentKey(selected.value === null ? null : selected.value.id)
    treeRef.value?.filter(keyword.value)
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  treeRef.value?.filter(keyword.value)
}

function handleNodeClick(data: OrganizationTree) {
  selected.value = data
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
  parent_id: undefined as number | undefined,
  org_type: 'DEPT' as OrganizationPayload['org_type'],
  leader: '',
  phone: '',
  sort_order: 0,
  is_enabled: true,
  remark: '',
})

const rules: FormRules = {
  code: [{ required: true, message: '请输入组织编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入组织名称', trigger: 'blur' }],
}

/** 编辑时不能把自己及自己的下级选为上级组织，这里把整棵子树剔除 */
const parentOptions = computed<OrganizationTree[]>(() => {
  const id = editingId.value
  return id === null ? treeData.value : excludeSubtree(treeData.value, id)
})

function excludeSubtree(nodes: OrganizationTree[], id: number): OrganizationTree[] {
  return nodes
    .filter((node) => node.id !== id)
    .map((node) => ({ ...node, children: excludeSubtree(node.children, id) }))
}

function resetForm() {
  form.code = ''
  form.name = ''
  form.parent_id = undefined
  form.org_type = 'DEPT'
  form.leader = ''
  form.phone = ''
  form.sort_order = 0
  form.is_enabled = true
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openCreateChild(row: OrganizationTree) {
  openCreate()
  form.parent_id = row.id
}

function openEdit(row: OrganizationTree) {
  editingId.value = row.id
  form.code = row.code
  form.name = row.name
  form.parent_id = row.parent_id ?? undefined
  form.org_type = row.org_type
  form.leader = row.leader ?? ''
  form.phone = row.phone ?? ''
  form.sort_order = row.sort_order
  form.is_enabled = row.is_enabled
  form.remark = row.remark ?? ''
  dialogVisible.value = true
}

/** 空串统一转成 null，避免把空值写成字符串 */
function buildPayload(): OrganizationPayload {
  return {
    code: form.code,
    name: form.name,
    parent_id: form.parent_id ?? null,
    org_type: form.org_type,
    leader: form.leader || null,
    phone: form.phone || null,
    sort_order: form.sort_order,
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
      await createOrganization(buildPayload())
      ElMessage.success('新增成功')
    } else {
      await updateOrganization(editingId.value, buildPayload())
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

/** 存在下级或组织下有人时后端会拒绝并返回原因，直接展示即可 */
async function handleDelete(row: OrganizationTree) {
  await ElMessageBox.confirm(`确定删除组织「${row.name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      try {
        await deleteOrganization(row.id)
        ElMessage.success('删除成功')
        if (selected.value?.id === row.id) {
          selected.value = null
        }
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
  <el-row :gutter="12">
    <el-col :span="9">
      <el-form :inline="true" class="panel__query">
        <el-form-item label="关键词">
          <el-input
            v-model="keyword"
            placeholder="编码 / 名称 / 负责人"
            clearable
            style="width: 180px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
        </el-form-item>
      </el-form>

      <div class="panel__toolbar">
        <el-button type="primary" @click="openCreate">新增根组织</el-button>
        <span class="panel__count">共 {{ nodeCount }} 个组织</span>
      </div>

      <el-tree
        ref="treeRef"
        v-loading="loading"
        class="org-tree"
        :data="treeData"
        node-key="id"
        highlight-current
        default-expand-all
        :expand-on-click-node="false"
        :props="{ label: 'name', children: 'children' }"
        :filter-node-method="filterNode"
        @node-click="handleNodeClick"
      >
        <template #default="{ data }">
          <span class="org-node">
            <span>{{ data.name }}</span>
            <el-tag size="small" :type="ORG_TYPE_TAGS[data.org_type as keyof typeof ORG_TYPE_TAGS]">
              {{ ORG_TYPE_LABELS[data.org_type as keyof typeof ORG_TYPE_LABELS] }}
            </el-tag>
            <el-tag v-if="!data.is_enabled" size="small" type="info">停用</el-tag>
          </span>
        </template>
      </el-tree>
    </el-col>

    <el-col :span="15">
      <el-empty v-if="selected === null" description="请先在左侧选择组织节点" />
      <template v-else>
        <div class="panel__toolbar">
          <el-button type="primary" @click="openCreateChild(selected)">新增下级</el-button>
          <el-button @click="openEdit(selected)">编辑</el-button>
          <el-button type="danger" @click="handleDelete(selected)">删除</el-button>
        </div>

        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="组织编码">{{ selected.code }}</el-descriptions-item>
          <el-descriptions-item label="组织名称">{{ selected.name }}</el-descriptions-item>
          <el-descriptions-item label="组织类型">
            <el-tag size="small" :type="ORG_TYPE_TAGS[selected.org_type]">
              {{ ORG_TYPE_LABELS[selected.org_type] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="层级">{{ selected.level }}</el-descriptions-item>
          <el-descriptions-item label="层级路径">{{ selected.path }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ selected.leader ?? '——' }}</el-descriptions-item>
          <el-descriptions-item label="联系电话">{{ selected.phone ?? '——' }}</el-descriptions-item>
          <el-descriptions-item label="排序">{{ selected.sort_order }}</el-descriptions-item>
          <el-descriptions-item label="是否启用">
            <el-tag size="small" :type="selected.is_enabled ? 'success' : 'info'">
              {{ selected.is_enabled ? '启用' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ selected.remark ?? '——' }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-col>
  </el-row>

  <el-dialog
    v-model="dialogVisible"
    :title="editingId === null ? '新增组织' : '编辑组织'"
    width="620px"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="组织编码" prop="code">
            <el-input v-model="form.code" placeholder="如 D-001" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="组织名称" prop="name">
            <el-input v-model="form.name" placeholder="如 制造部" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="上级组织">
            <el-tree-select
              v-model="form.parent_id"
              :data="parentOptions"
              node-key="id"
              check-strictly
              clearable
              :props="{ label: 'name', children: 'children' }"
              placeholder="不选表示根组织"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="组织类型">
            <el-select v-model="form.org_type" style="width: 100%">
              <el-option
                v-for="item in ORG_TYPE_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="负责人">
            <el-input v-model="form.leader" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="联系电话">
            <el-input v-model="form.phone" />
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

.org-tree {
  min-height: 360px;
}

.org-node {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
