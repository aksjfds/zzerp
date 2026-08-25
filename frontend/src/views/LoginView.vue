<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDefaultDashboardPath } from '@/permission/defaultRoute'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeAccount = ref('')
const accounts = [
  { username: 'admin', name: '系统管理', description: '系统配置与全局管理' },
  { username: 'engineering', name: '工程部', description: '产品、BOM 与生产流程' },
  { username: 'business', name: '业务部', description: '客户订单与生产计划' },
  { username: 'pmc', name: 'PMC部门', description: '生产进度查看' },
  { username: 'stamp', name: '冲压部', description: '冲压工艺生产' },
  { username: 'cnc', name: '机加部', description: '机加工艺生产' },
  { username: 'polish', name: '表面处理部', description: '表面处理工艺生产' },
  { username: 'outsource', name: '外协部', description: '蚀字、电镀外协工单' },
  { username: 'qc', name: 'QC部门', description: '质量检验与放行' },
  { username: 'assembly', name: '装配部', description: '装配生产' },
  { username: 'finished', name: '成品部', description: '成品入库与订单发货' },
  { username: 'warehouse', name: '仓库', description: '配件、装配体库存管理' },
] as const

async function loginAs(username: string) {
  activeAccount.value = username
  try {
    const user = await authStore.login({ username, password: '1' })
    const defaultPath = getDefaultDashboardPath(user)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : defaultPath
    await router.replace(redirect)
  } catch {
    ElMessage.error(`${username} 账号登录失败`)
  } finally {
    activeAccount.value = ''
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

      <div class="account-heading">
        <h2>选择登录账号</h2>
        <p>点击部门账号直接进入对应工作台</p>
      </div>
      <div class="account-grid">
        <button
          v-for="account in accounts"
          :key="account.username"
          class="account-card"
          type="button"
          :disabled="authStore.loading"
          @click="loginAs(account.username)"
        >
          <span class="account-avatar">{{ account.name.slice(0, 1) }}</span>
          <span class="account-copy">
            <strong>{{ account.name }}</strong>
            <small>{{ account.username }}</small>
            <span>{{ account.description }}</span>
          </span>
          <span v-if="activeAccount === account.username" class="account-state">登录中…</span>
          <span v-else class="account-arrow">进入</span>
        </button>
      </div>
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
  width: min(920px, 100%);
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

.account-heading {
  margin-bottom: 16px;
}

.account-heading h2 { margin: 0; font-size: 18px; }
.account-heading p { margin: 5px 0 0; color: var(--erp-text-muted); font-size: 13px; }
.account-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.account-card {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 92px;
  padding: 14px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-low);
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
  transition: border-color .16s ease, background .16s ease, transform .16s ease;
}
.account-card:hover:not(:disabled) { border-color: var(--md-primary); background: var(--md-primary-container); transform: translateY(-1px); }
.account-card:disabled { cursor: wait; opacity: .72; }
.account-avatar { display: grid; width: 42px; height: 42px; place-items: center; border-radius: 13px; background: var(--md-primary); color: var(--md-on-primary); font-weight: 700; }
.account-copy { display: grid; min-width: 0; gap: 2px; }
.account-copy strong { font-size: 15px; }
.account-copy small { color: var(--md-primary); font-weight: 600; }
.account-copy > span { overflow: hidden; color: var(--erp-text-muted); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.account-arrow, .account-state { color: var(--md-primary); font-size: 12px; font-weight: 700; white-space: nowrap; }
@media (max-width: 780px) {
  .account-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 480px) {
  .login-page { padding: 12px; }
  .login-panel { padding: 24px 20px; border-radius: 24px; }
  .account-grid { grid-template-columns: 1fr; }
}
</style>
