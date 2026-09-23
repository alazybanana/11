/**
 * system 模块 —— 系统操作日志接口（只读查询 + 超管清理）。
 */

import type { PageData } from '@/types/api'
import { del, get } from '@/utils/request'

import type { OperationLog, OperationLogQuery } from './types'

/** 操作日志分页查询 */
export function listOperationLogs(query: OperationLogQuery): Promise<PageData<OperationLog>> {
  return get<PageData<OperationLog>>('/system/operation-logs', query)
}

/** 清理指定时间之前的日志（仅超级管理员），返回清理条数 */
export function clearOperationLogs(before: string): Promise<number> {
  return del<number>('/system/operation-logs', { params: { before } })
}
