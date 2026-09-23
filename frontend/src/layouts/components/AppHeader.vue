<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { changePassword } from '@/api/system'
import { useAppStore } from '@/stores/modules/app'
import { useAuthStore } from '@/stores/modules/auth'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()

const displayName = computed(
  () => authStore.user?.real_name || authStore.user?.username || '未登录',
)
const roleText = computed(() => {
  if (authStore.isSuperuser) {
    return '超级管理员'
  }
  const roles = authStore.user?.roles ?? []
  return roles.length ? roles.join(' / ') : '未分配角色'
})

const pwdVisible = ref(false)
const pwdSubmitting = ref(false)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6~64 位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.new_password) {
          callback(new Error('两次输入的新密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

function openPasswordDialog() {
  pwdForm.old_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm_password = ''
  pwdVisible.value = true
}

async function submitPassword() {
  const valid = await pwdFormRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  pwdSubmitting.value = true
  try {
    await changePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    pwdVisible.value = false
    await authStore.logout()
    await router.push('/login')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    pwdSubmitting.value = false
  }
}

async function handleLogout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning' })
    .then(async () => {
      await authStore.logout()
      await router.push('/login')
    })
    .catch(() => undefined)
}
</script>

<template>
  <div class="app-header">
    <el-button link type="primary" @click="appStore.toggleSidebar()">
      {{ appStore.sidebarCollapsed ? '展开菜单' : '收起菜单' }}
    </el-button>

    <span class="app-header__title">{{ route.meta.title ?? '' }}</span>

    <div class="app-header__right">
      <el-tag size="small" effect="plain">{{ roleText }}</el-tag>
      <span class="app-header__user">{{ displayName }}</span>
      <el-button link type="primary" @click="openPasswordDialog">修改密码</el-button>
      <el-button link type="danger" @click="handleLogout">退出登录</el-button>
    </div>

    <el-dialog v-model="pwdVisible" title="修改密码" width="420px">
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="80px">
        <el-form-item label="原密码" prop="old_password">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm_password">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="pwdSubmitting" @click="submitPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 0 16px;
}

.app-header__title {
  font-size: 15px;
  font-weight: 600;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.app-header__user {
  font-size: 13px;
  color: #303133;
}
</style>
