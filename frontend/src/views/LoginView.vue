<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { queryLoginAccounts } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { LoginAccount } from '@/types/auth'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const accounts = ref<LoginAccount[]>([])
const selectedUsername = ref('')
const accountsLoading = ref(false)

function getDefaultDashboardPath(department?: string) {
  if (!department || department === 'sys') return '/dashboard'
  return `/dashboard/${department}`
}

async function loadAccounts() {
  accountsLoading.value = true
  try {
    accounts.value = await queryLoginAccounts()
    selectedUsername.value = accounts.value[0]?.username ?? ''
  } catch {
    ElMessage.error('开发账号加载失败')
  } finally {
    accountsLoading.value = false
  }
}

async function submitLogin() {
  if (!selectedUsername.value) {
    ElMessage.warning('请选择登录账号')
    return
  }
  try {
    const user = await authStore.login({ username: selectedUsername.value })
    const defaultPath = getDefaultDashboardPath(user.department)
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : defaultPath
    router.replace(redirect)
  } catch {
    ElMessage.error('账号登录失败')
  }
}

onMounted(loadAccounts)
</script>

<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-brand">
        <div class="brand-mark">ZZ</div>
        <div>
          <h1>ZZ ERP</h1>
          <p>开发环境账号选择</p>
        </div>
      </div>

      <ElForm class="login-form" label-position="top" @submit.prevent="submitLogin">
        <ElFormItem label="登录账号">
          <ElSelect
            v-model="selectedUsername"
            v-loading="accountsLoading"
            filterable
            placeholder="请选择账号"
          >
            <ElOption
              v-for="account in accounts"
              :key="account.username"
              :label="`${account.departmentName} · ${account.username}`"
              :value="account.username"
            >
              <div class="account-option">
                <strong>{{ account.departmentName }}</strong>
                <span>{{ account.username }} · {{ account.role }}</span>
              </div>
            </ElOption>
          </ElSelect>
        </ElFormItem>
        <ElAlert
          title="开发模式：选择账号后直接建立登录会话，无需密码。"
          type="info"
          :closable="false"
          show-icon
        />
        <ElButton
          type="primary"
          native-type="submit"
          class="login-button"
          :loading="authStore.loading"
        >
          进入系统
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
    linear-gradient(135deg, rgb(37 99 235 / 12%), transparent 38%),
    linear-gradient(180deg, #f8fafc 0, #edf1f5 100%);
}
.login-panel {
  width: min(440px, 100%);
  padding: 30px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-md);
}
.login-brand { display: flex; gap: 14px; align-items: center; margin-bottom: 28px; }
.brand-mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-weight: 800;
}
.login-brand h1 { margin: 0; font-size: 24px; }
.login-brand p { margin: 4px 0 0; color: var(--erp-text-muted); font-size: 13px; }
.login-form { display: grid; gap: 12px; }
.login-form :deep(.el-select) { width: 100%; }
.account-option { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.account-option span { color: var(--el-text-color-secondary); font-size: 12px; }
.login-button { width: 100%; margin-top: 4px; }
</style>
