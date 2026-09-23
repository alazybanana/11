<script setup lang="ts">
import { ref } from 'vue'

import BomPanel from './panels/BomPanel.vue'
import DictionaryPanel from './panels/DictionaryPanel.vue'
import EmployeePanel from './panels/EmployeePanel.vue'
import MaterialPanel from './panels/MaterialPanel.vue'
import OperationLogPanel from './panels/OperationLogPanel.vue'
import OrganizationPanel from './panels/OrganizationPanel.vue'
import PermissionPanel from './panels/PermissionPanel.vue'
import RolePanel from './panels/RolePanel.vue'
import RoutingPanel from './panels/RoutingPanel.vue'
import UserPanel from './panels/UserPanel.vue'

/**
 * 系统与基础信息管理。
 *
 * 六个标签页对应课程设计要求的六项功能：
 * 1. 产品信息管理（物料 / BOM，物料按类型区分成品、半成品、原材料）
 * 2. 工艺信息管理（工艺路线 + 工序）
 * 3. 组织与人员信息管理（组织结构树 / 人员档案）
 * 4. 共性基础字典管理（字典类型 / 字典项）
 * 5. 系统访问权限管理（账号 / 角色与访问范围 / 权限资源）
 * 6. 系统操作日志管理
 */
const activeTab = ref('product')
</script>

<template>
  <el-tabs v-model="activeTab" type="border-card" class="system-page">
    <el-tab-pane label="产品信息管理" name="product">
      <el-tabs type="card" class="system-page__inner">
        <el-tab-pane label="物料主数据">
          <MaterialPanel />
        </el-tab-pane>
        <el-tab-pane label="BOM 建立与维护">
          <BomPanel />
        </el-tab-pane>
      </el-tabs>
    </el-tab-pane>

    <el-tab-pane label="工艺信息管理" name="routing">
      <RoutingPanel />
    </el-tab-pane>

    <el-tab-pane label="组织与人员管理" name="organization">
      <el-tabs type="card" class="system-page__inner">
        <el-tab-pane label="组织结构树">
          <OrganizationPanel />
        </el-tab-pane>
        <el-tab-pane label="人员档案">
          <EmployeePanel />
        </el-tab-pane>
      </el-tabs>
    </el-tab-pane>

    <el-tab-pane label="共性基础字典" name="dictionary">
      <DictionaryPanel />
    </el-tab-pane>

    <el-tab-pane label="访问权限管理" name="access">
      <el-tabs type="card" class="system-page__inner">
        <el-tab-pane label="账号管理">
          <UserPanel />
        </el-tab-pane>
        <el-tab-pane label="角色与访问范围">
          <RolePanel />
        </el-tab-pane>
        <el-tab-pane label="权限资源">
          <PermissionPanel />
        </el-tab-pane>
      </el-tabs>
    </el-tab-pane>

    <el-tab-pane label="操作日志" name="log">
      <OperationLogPanel />
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.system-page {
  background-color: #ffffff;
}

.system-page__inner {
  margin-top: -8px;
}

.system-page__inner :deep(.el-tabs__header) {
  margin-bottom: 12px;
}
</style>
