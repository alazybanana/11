/**
 * system 模块 —— 健康检查（占位接口，用于验证前后端连通性）。
 */

import type { HealthData } from '@/types/api'
import { get } from '@/utils/request'

export function getSystemHealth(): Promise<HealthData> {
  return get<HealthData>('/system/health')
}
