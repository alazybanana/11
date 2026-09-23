/**
 * system 模块 —— 产品信息管理接口：物料主数据、BOM（头 + 行）、多层 BOM 展开。
 *
 * 成品 / 半成品 / 原材料统一由「物料主数据」维护；
 * BOM 的父件与子件都引用物料，因此 BOM 支持任意层数。
 */

import type { PageData } from '@/types/api'
import { del, get, post, put } from '@/utils/request'

import type {
  Bom,
  BomDetail,
  BomExpandQuery,
  BomLine,
  BomLinePayload,
  BomPayload,
  BomQuery,
  BomTreeNode,
  Material,
  MaterialPayload,
  MaterialQuery,
} from './types'

// --------------------------------------------------------------------------- #
// 物料主数据
// --------------------------------------------------------------------------- #
export function listMaterials(query: MaterialQuery): Promise<PageData<Material>> {
  return get<PageData<Material>>('/system/materials', query)
}

export function getMaterial(id: number): Promise<Material> {
  return get<Material>(`/system/materials/${id}`)
}

export function createMaterial(payload: MaterialPayload): Promise<Material> {
  return post<Material>('/system/materials', payload)
}

export function updateMaterial(id: number, payload: Partial<MaterialPayload>): Promise<Material> {
  return put<Material>(`/system/materials/${id}`, payload)
}

export function deleteMaterial(id: number): Promise<void> {
  return del<void>(`/system/materials/${id}`)
}

// --------------------------------------------------------------------------- #
// BOM 头
// --------------------------------------------------------------------------- #
export function listBoms(query: BomQuery): Promise<PageData<Bom>> {
  return get<PageData<Bom>>('/system/boms', query)
}

export function getBom(id: number): Promise<Bom> {
  return get<Bom>(`/system/boms/${id}`)
}

/** BOM 详情：含行明细 */
export function getBomDetail(id: number): Promise<BomDetail> {
  return get<BomDetail>(`/system/boms/${id}/detail`)
}

export function createBom(payload: BomPayload): Promise<Bom> {
  return post<Bom>('/system/boms', payload)
}

export function updateBom(id: number, payload: Partial<BomPayload>): Promise<Bom> {
  return put<Bom>(`/system/boms/${id}`, payload)
}

export function deleteBom(id: number): Promise<void> {
  return del<void>(`/system/boms/${id}`)
}

// --------------------------------------------------------------------------- #
// BOM 行
// --------------------------------------------------------------------------- #
export function listBomLines(bomId: number): Promise<BomLine[]> {
  return get<BomLine[]>(`/system/boms/${bomId}/lines`)
}

export function createBomLine(bomId: number, payload: BomLinePayload): Promise<BomLine> {
  return post<BomLine>(`/system/boms/${bomId}/lines`, payload)
}

export function updateBomLine(
  bomId: number,
  lineId: number,
  payload: Partial<BomLinePayload>,
): Promise<BomLine> {
  return put<BomLine>(`/system/boms/${bomId}/lines/${lineId}`, payload)
}

export function deleteBomLine(bomId: number, lineId: number): Promise<void> {
  return del<void>(`/system/boms/${bomId}/lines/${lineId}`)
}

// --------------------------------------------------------------------------- #
// 多层 BOM 展开（层数不限）
// --------------------------------------------------------------------------- #
/** 按物料把多层 BOM 展开成树，顶层为传入的物料 */
export function getBomTree(materialId: number, query: BomExpandQuery = {}): Promise<BomTreeNode> {
  return get<BomTreeNode>('/system/boms/tree', { material_id: materialId, ...query })
}

/** 按物料把多层 BOM 展开成一维用料清单（虚拟件穿透），供 MRP 使用 */
export function getBomFlatLines(
  materialId: number,
  query: BomExpandQuery = {},
): Promise<BomTreeNode[]> {
  return get<BomTreeNode[]>('/system/boms/flat-lines', { material_id: materialId, ...query })
}