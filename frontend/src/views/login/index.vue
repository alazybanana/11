<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { listRegisterRoles, register } from '@/api/system'
import type { RegisterPayload, RoleOption } from '@/api/system/types'
import { useAuthStore } from '@/stores/modules/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入登录账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) {
    return
  }

  submitting.value = true
  try {
    const user = await authStore.login({ ...form })
    if (user.approval_status === 'PENDING') {
      ElMessage.warning('你的注册申请还未被批准，当前仅有游客权限')
    } else {
      ElMessage.success(`欢迎回来，${user.real_name || user.username}`)
    }
    const redirect = route.query.redirect
    await router.push(typeof redirect === 'string' && redirect ? redirect : '/dashboard')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    submitting.value = false
  }
}

// --------------------------------------------------------------------------- #
// 注册
// --------------------------------------------------------------------------- #
const registerVisible = ref(false)
const registerFormRef = ref<FormInstance>()
const registerSubmitting = ref(false)
const roleOptions = ref<RoleOption[]>([])

const registerForm = reactive({
  username: '',
  password: '',
  password2: '',
  real_name: '',
  email: '',
  phone: '',
  role_id: undefined as number | undefined,
})

const registerRules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    { min: 3, max: 64, message: '账号长度需为 3~64 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度需为 6~64 位', trigger: 'blur' },
  ],
  password2: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        callback(value === registerForm.password ? undefined : new Error('两次输入的密码不一致'))
      },
      trigger: 'blur',
    },
  ],
  role_id: [{ required: true, message: '请选择要申请的身份', trigger: 'change' }],
}

async function openRegister() {
  registerVisible.value = true
  registerForm.username = form.username
  registerForm.password = ''
  registerForm.password2 = ''
  registerForm.real_name = ''
  registerForm.email = ''
  registerForm.phone = ''
  registerForm.role_id = undefined
  if (roleOptions.value.length === 0) {
    try {
      roleOptions.value = await listRegisterRoles()
    } catch (error) {
      ElMessage.error((error as Error).message)
    }
  }
}

async function handleRegister() {
  const valid = await registerFormRef.value?.validate().catch(() => false)
  if (!valid || registerForm.role_id === undefined) {
    return
  }

  registerSubmitting.value = true
  try {
    const payload: RegisterPayload = {
      username: registerForm.username,
      password: registerForm.password,
      real_name: registerForm.real_name || null,
      email: registerForm.email || null,
      phone: registerForm.phone || null,
      role_id: registerForm.role_id,
    }
    await register(payload)
    // 注册即登录：先相信他，但审批通过前只有游客权限
    await authStore.login({ username: registerForm.username, password: registerForm.password })
    const roleName = roleOptions.value.find((item) => item.id === registerForm.role_id)?.name ?? ''
    ElMessage.success(`注册成功，已登录。待人事主管批准后获得「${roleName}」权限`)
    registerVisible.value = false
    await router.push('/dashboard')
  } catch (error) {
    ElMessage.error((error as Error).message)
  } finally {
    registerSubmitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-page__card" shadow="never">
      <template #header>
        <span class="login-page__title">BH-ERP 登录</span>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="72px"
        @keyup.enter="handleSubmit"
      >
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" placeholder="请输入登录账号" clearable />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>

        <el-button class="login-page__button" type="primary" :loading="submitting" @click="handleSubmit">
          登录
        </el-button>
      </el-form>

      <div class="login-page__register">
        没有账号？
        <el-link type="primary" @click="openRegister">注册账号</el-link>
        <span class="login-page__tip-inline">（自选身份，人事主管批准后生效）</span>
      </div>
    </el-card>

    <el-dialog v-model="registerVisible" title="注册账号" width="480px" append-to-body>
      <el-form ref="registerFormRef" :model="registerForm" :rules="registerRules" label-width="88px">
        <el-form-item label="登录账号" prop="username">
          <el-input v-model="registerForm.username" placeholder="3~64 位" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="registerForm.password" type="password" placeholder="6~64 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="password2">
          <el-input v-model="registerForm.password2" type="password" placeholder="再次输入密码" show-password />
        </el-form-item>
        <el-form-item label="申请身份" prop="role_id">
          <el-select v-model="registerForm.role_id" placeholder="请选择要申请的身份" style="width: 100%">
            <el-option
              v-for="role in roleOptions"
              :key="role.id"
              :label="`${role.name}（${role.code}）`"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="registerForm.real_name" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="registerForm.email" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="registerForm.phone" />
        </el-form-item>
      </el-form>

      <p class="register-tip">
        注册后即可登录，但审批通过前只有游客权限；人事主管批准后，你申请的身份权限才会生效。
      </p>

      <template #footer>
        <el-button @click="registerVisible = false">取消</el-button>
        <el-button type="primary" :loading="registerSubmitting" @click="handleRegister">
          注册并登录
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  background-color: #f5f7fa;
}

.login-page__card {
  width: 420px;
}

.login-page__title {
  font-size: 16px;
  font-weight: 600;
}

.login-page__button {
  width: 100%;
  margin-top: 4px;
}

.login-page__register {
  margin-top: 16px;
  font-size: 13px;
  text-align: center;
  color: #606266;
}

.login-page__tip-inline {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.register-tip {
  margin: 4px 0 0;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #909399;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>