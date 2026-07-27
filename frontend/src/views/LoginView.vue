<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDefaultDashboardPath } from '@/permission/defaultRoute'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const loginForm = reactive({
  username: '',
  password: '',
})

async function submitLogin() {
  if (!loginForm.username.trim() || !loginForm.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  try {
    const user = await authStore.login(loginForm)
    const defaultPath = getDefaultDashboardPath(user)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : defaultPath
    router.replace(redirect)
  } catch {
    ElMessage.error('用户名或密码错误')
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <div class="brand-mark">ZZ</div>
        <div>
          <h1>ZZ ERP</h1>
          <p>部门操作工作台</p>
        </div>
      </div>

      <ElForm class="login-form" :model="loginForm" label-position="top" @keyup.enter="submitLogin">
        <ElFormItem label="用户名">
          <ElInput v-model="loginForm.username" clearable placeholder="请输入部门账号" />
        </ElFormItem>
        <ElFormItem label="密码">
          <ElInput v-model="loginForm.password" type="password" show-password placeholder="请输入密码" />
        </ElFormItem>
        <ElButton type="primary" class="login-button" :loading="authStore.loading" @click="submitLogin">
          登录
        </ElButton>
      </ElForm>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at 12% 10%, var(--md-primary-container), transparent 34%),
    radial-gradient(circle at 88% 90%, var(--md-tertiary-container), transparent 30%),
    var(--md-surface);
}

.login-panel {
  width: min(420px, 100%);
  padding: 30px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 28px;
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-md);
}

.login-brand {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 28px;
}

.brand-mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 14px;
  background: var(--md-primary);
  color: var(--md-on-primary);
  font-weight: 800;
}

.login-brand h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -.02em;
}

.login-brand p {
  margin: 4px 0 0;
  color: var(--erp-text-muted);
  font-size: 13px;
}

.login-form {
  display: grid;
  gap: 8px;
}

.login-button {
  width: 100%;
  margin-top: 6px;
}
@media (max-width: 480px) {
  .login-page { padding: 12px; }
  .login-panel { padding: 24px 20px; border-radius: 24px; }
}
</style>
