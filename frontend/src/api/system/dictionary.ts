/**
 * system 模块 —— 共性基础字典接口（字典类型 + 字典项）。
 */

import type { PageData } from '@/types/api'
import { del, get, post, put } from '@/utils/request'

import type {
  DictionaryItem,
  DictionaryItemPayload,
  DictionaryItemQuery,
  DictionaryType,
  DictionaryTypePayload,
  DictionaryTypeQuery,
} from './types'

// --------------------------------------------------------------------------- #
// 字典类型
// --------------------------------------------------------------------------- #
export function listDictionaryTypes(
  query: DictionaryTypeQuery,
): Promise<PageData<DictionaryType>> {
  return get<PageData<DictionaryType>>('/system/dictionary-types', query)
}

export function getDictionaryType(id: number): Promise<DictionaryType> {
  return get<DictionaryType>(`/system/dictionary-types/${id}`)
}

export function createDictionaryType(payload: DictionaryTypePayload): Promise<DictionaryType> {
  return post<DictionaryType>('/system/dictionary-types', payload)
}

export function updateDictionaryType(
  id: number,
  payload: Partial<DictionaryTypePayload>,
): Promise<DictionaryType> {
  return put<DictionaryType>(`/system/dictionary-types/${id}`, payload)
}

export function deleteDictionaryType(id: number): Promise<void> {
  return del<void>(`/system/dictionary-types/${id}`)
}

// --------------------------------------------------------------------------- #
// 字典项
// --------------------------------------------------------------------------- #
/** 字典项分页查询（可按字典类型过滤） */
export function listDictionaryItems(
  query: DictionaryItemQuery,
): Promise<PageData<DictionaryItem>> {
  return get<PageData<DictionaryItem>>('/system/dictionary-items', query)
}

/** 在指定字典类型下新增字典项 */
export function createDictionaryItem(
  typeId: number,
  payload: DictionaryItemPayload,
): Promise<DictionaryItem> {
  return post<DictionaryItem>(`/system/dictionary-types/${typeId}/items`, payload)
}

export function updateDictionaryItem(
  itemId: number,
  payload: Partial<DictionaryItemPayload>,
): Promise<DictionaryItem> {
  return put<DictionaryItem>(`/system/dictionary-items/${itemId}`, payload)
}

export function deleteDictionaryItem(itemId: number): Promise<void> {
  return del<void>(`/system/dictionary-items/${itemId}`)
}
