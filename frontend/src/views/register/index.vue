<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { listRoles, register } from '@/api/system'
import type { Role } from '@/types/erp'

const router = useRouter()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const rolesLoading = ref(false)
const roleOptions = ref<Role[]>([])

const form = reactive({
  username: '',
  display_name: '',
  password: '',
  password2: '',
  role_ids: [] as number[],
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6~64 位', trigger: 'blur' },
  ],
  password2: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        callback(value === form.password ? undefined : new Error('两次输入的密码不一致'))
      },
      trigger: 'blur',
    },
  ],
  role_ids: [
    { required: true, type: 'array', min: 1, message: '请至少选择一种身份', trigger: 'change' },
  ],
}

onMounted(async () => {
  rolesLoading.value = true
  try {
    roleOptions.value = await listRoles()
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    rolesLoading.value = false
  }
})

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    await register({
      username: form.username,
      password: form.password,
      display_name: form.display_name,
      role_ids: form.role_ids,
    })
    ElMessage.success('注册成功，请使用新账号登录')
    router.replace({ path: '/login', query: { username: form.username } })
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <el-card class="register-page__card" shadow="never">
      <template #header>
        <span class="register-page__title">BH-ERP 账号注册</span>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="0">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item prop="display_name">
          <el-input v-model="form.display_name" placeholder="显示名（姓名）" size="large" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少 6 位）"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item prop="password2">
          <el-input
            v-model="form.password2"
            type="password"
            placeholder="确认密码"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item label="选择身份" label-width="80px" prop="role_ids">
          <el-checkbox-group v-model="form.role_ids" class="register-page__roles">
            <el-checkbox
              v-for="role in roleOptions"
              :key="role.id"
              :value="role.id"
              class="register-page__role"
            >
              <div class="register-page__role-name">{{ role.role_name }}</div>
              <div v-if="role.description" class="register-page__role-desc">{{ role.description }}</div>
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-button
          class="register-page__button"
          type="primary"
          size="large"
          :loading="submitting || rolesLoading"
          @click="submit"
        >
          注 册
        </el-button>
      </el-form>

      <el-divider />

      <div class="register-page__footer">
        <span>已有账号？</span>
        <router-link class="register-page__link" to="/login">去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.register-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100%;
  padding: 24px 0;
  background-color: #f5f7fa;
}

.register-page__card {
  width: 480px;
}

.register-page__title {
  font-size: 16px;
  font-weight: 600;
}

.register-page__roles {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
}

.register-page__role {
  height: auto;
  align-items: flex-start;
  margin-right: 0;
}

.register-page__role-name {
  font-weight: 500;
}

.register-page__role-desc {
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
  white-space: normal;
}

.register-page__button {
  width: 100%;
}

.register-page__footer {
  text-align: center;
  color: #909399;
  font-size: 13px;
}

.register-page__link {
  margin-left: 4px;
  color: #409eff;
  text-decoration: none;
}
</style>