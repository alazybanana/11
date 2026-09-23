<script setup lang="ts">
/**
 * 系统操作日志查询（只读）。
 *
 * 标准列表页结构：查询条件 → 工具栏 → 表格 → 分页 → 详情弹窗。
 * 日志不可新增 / 修改 / 删除，仅超级管理员可清理历史日志。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { clearOperationLogs, listOperationLogs } from '@/api/system'
import type { OperationLog, OperationLogQuery } from '@/api/system/types'
import { useAuthStore } from '@/stores/modules/auth'
import {
  LOG_STATUS_LABELS,
  LOG_STATUS_OPTIONS,
  LOG_STATUS_TAGS,
  OPERATION_ACTION_LABELS,
  OPERATION_ACTION_OPTIONS,
  OPERATION_ACTION_TAGS,
} from '@/views/system/options'

const authStore = useAuthStore()

const loading = ref(false)
const rows = ref<OperationLog[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  module: '',
  action: '' as OperationLogQuery['action'] | '',
  status: '' as OperationLogQuery['status'] | '',
  username: '',
})

/** 操作时间范围，拆成 created_from / created_to 两个参数 */
const timeRange = ref<[string, string] | null>(null)

/** 只把有值的条件发到后端，空串统一丢掉 */
function buildQuery(): OperationLogQuery {
  const params: OperationLogQuery = { page: query.page, page_size: query.page_size }
  if (query.keyword) params.keyword = query.keyword
  if (query.module) params.module = query.module
  if (query.action) params.action = query.action
  if (query.status) params.status = query.status
  if (query.username) params.username = query.username
  if (timeRange.value !== null) {
    params.created_from = timeRange.value[0]
    params.created_to = timeRange.value[1]
  }
  return params
}

async function load() {
  loading.value = true
  try {
    const data = await listOperationLogs(buildQuery())
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
  query.module = ''
  query.action = ''
  query.status = ''
  query.username = ''
  timeRange.value = null
  handleSearch()
}

// --------------------------------------------------------------------------- #
// 详情
// --------------------------------------------------------------------------- #
const detailVisible = ref(false)
const detail = ref<OperationLog | null>(null)

function openDetail(row: OperationLog) {
  detail.value = row
  detailVisible.value = true
}

// --------------------------------------------------------------------------- #
// 清理历史日志（仅超级管理员）
// --------------------------------------------------------------------------- #
function handleClear() {
  ElMessageBox.prompt('请输入时间点，该时间之前的日志将被清理', '清理历史日志', {
    inputPlaceholder: 'YYYY-MM-DDTHH:mm:ss',
    inputPattern: /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/,
    inputErrorMessage: '时间格式需为 YYYY-MM-DDTHH:mm:ss',
  })
    .then(async ({ value }) => {
      try {
        const count = await clearOperationLogs(value)
        ElMessage.success(`已清理 ${count} 条日志`)
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
          placeholder="操作人 / 路径 / 描述"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="所属模块">
        <el-input
          v-model="query.module"
          placeholder="如 system"
          clearable
          style="width: 140px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="动作类型">
        <el-select v-model="query.action" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in OPERATION_ACTION_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="结果">
        <el-select v-model="query.status" placeholder="全部" clearable style="width: 110px">
          <el-option
            v-for="item in LOG_STATUS_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="操作人账号">
        <el-input
          v-model="query.username"
          placeholder="如 admin"
          clearable
          style="width: 140px"
          @keyup.enter="handleSearch"
        />
      </el-form-item>
      <el-form-item label="操作时间">
        <el-date-picker
          v-model="timeRange"
          type="datetimerange"
          value-format="YYYY-MM-DDTHH:mm:ss"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          style="width: 360px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <div class="panel__toolbar">
      <span class="panel__count">共 {{ total }} 条</span>
      <el-button
        v-if="authStore.isSuperuser"
        type="danger"
        class="panel__toolbar-right"
        @click="handleClear"
      >
        清理历史日志
      </el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe size="small">
      <el-table-column prop="created_at" label="操作时间" width="170" />
      <el-table-column prop="username" label="操作人" width="100" />
      <el-table-column prop="module" label="模块" width="100" />
      <el-table-column label="动作" width="80">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="OPERATION_ACTION_TAGS[row.action as keyof typeof OPERATION_ACTION_TAGS]"
          >
            {{ OPERATION_ACTION_LABELS[row.action as keyof typeof OPERATION_ACTION_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column prop="method" label="方法" width="80" />
      <el-table-column prop="path" label="请求路径" min-width="200" show-overflow-tooltip />
      <el-table-column prop="ip" label="客户端 IP" width="130" />
      <el-table-column prop="duration_ms" label="耗时(ms)" width="90" />
      <el-table-column label="结果" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="LOG_STATUS_TAGS[row.status as keyof typeof LOG_STATUS_TAGS]">
            {{ LOG_STATUS_LABELS[row.status as keyof typeof LOG_STATUS_LABELS] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">查看详情</el-button>
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

    <el-dialog v-model="detailVisible" title="日志详情" width="640px">
      <el-descriptions v-if="detail !== null" :column="1" border size="small">
        <el-descriptions-item label="操作时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ detail.username ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ detail.module ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="动作">
          {{
            OPERATION_ACTION_LABELS[detail.action as keyof typeof OPERATION_ACTION_LABELS]
          }}
        </el-descriptions-item>
        <el-descriptions-item label="描述">{{ detail.description ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="HTTP 方法">{{ detail.method ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="请求路径">{{ detail.path ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="客户端 IP">{{ detail.ip ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="耗时(ms)">{{ detail.duration_ms ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="结果">
          {{ LOG_STATUS_LABELS[detail.status as keyof typeof LOG_STATUS_LABELS] }}
        </el-descriptions-item>
      </el-descriptions>

      <div class="panel__detail-label">请求参数</div>
      <el-input :model-value="detail?.request_params ?? ''" type="textarea" :rows="4" readonly />

      <div class="panel__detail-label">错误信息</div>
      <el-input :model-value="detail?.error_msg ?? ''" type="textarea" :rows="3" readonly />

      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
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

.panel__toolbar-right {
  margin-left: auto;
}

.panel__detail-label {
  margin: 10px 0 4px;
  font-size: 13px;
  color: #606266;
}
</style>
