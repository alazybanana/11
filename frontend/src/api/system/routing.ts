/**
 * system 模块 —— 工艺信息管理接口：工艺路线（头 + 工序）。
 */

import type { PageData } from '@/types/api'
import { del, get, post, put } from '@/utils/request'

import type {
  Routing,
  RoutingDetail,
  RoutingPayload,
  RoutingQuery,
  RoutingStep,
  RoutingStepPayload,
} from './types'

// --------------------------------------------------------------------------- #
// 工艺路线头
// --------------------------------------------------------------------------- #
export function listRoutings(query: RoutingQuery): Promise<PageData<Routing>> {
  return get<PageData<Routing>>('/system/routings', query)
}

export function getRouting(id: number): Promise<Routing> {
  return get<Routing>(`/system/routings/${id}`)
}

/** 工艺路线详情：含工序明细 */
export function getRoutingDetail(id: number): Promise<RoutingDetail> {
  return get<RoutingDetail>(`/system/routings/${id}/detail`)
}

export function createRouting(payload: RoutingPayload): Promise<Routing> {
  return post<Routing>('/system/routings', payload)
}

export function updateRouting(id: number, payload: Partial<RoutingPayload>): Promise<Routing> {
  return put<Routing>(`/system/routings/${id}`, payload)
}

export function deleteRouting(id: number): Promise<void> {
  return del<void>(`/system/routings/${id}`)
}

// --------------------------------------------------------------------------- #
// 工序
// --------------------------------------------------------------------------- #
export function listRoutingSteps(routingId: number): Promise<RoutingStep[]> {
  return get<RoutingStep[]>(`/system/routings/${routingId}/steps`)
}

export function createRoutingStep(
  routingId: number,
  payload: RoutingStepPayload,
): Promise<RoutingStep> {
  return post<RoutingStep>(`/system/routings/${routingId}/steps`, payload)
}

export function updateRoutingStep(
  routingId: number,
  stepId: number,
  payload: Partial<RoutingStepPayload>,
): Promise<RoutingStep> {
  return put<RoutingStep>(`/system/routings/${routingId}/steps/${stepId}`, payload)
}

export function deleteRoutingStep(routingId: number, stepId: number): Promise<void> {
  return del<void>(`/system/routings/${routingId}/steps/${stepId}`)
}
