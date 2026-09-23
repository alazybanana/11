/**
 * system 模块（系统与基础信息管理）接口统一出口。
 *
 * 业务页面统一从这里导入，例如：
 * ```ts
 * import { listMaterials, createMaterial } from '@/api/system'
 * ```
 * 类型单独从 `@/api/system/types` 导入。
 */

export * from './types'

export * from './auth'
export * from './material'
export * from './routing'
export * from './organization'
export * from './dictionary'
export * from './access'
export * from './log'

export { getSystemHealth } from './health'
