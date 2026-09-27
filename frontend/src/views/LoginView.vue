<script setup lang="ts">
import { onMounted, ref } from 'vue'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDefaultDashboardPath } from '@/permission/defaultRoute'
import { erpMotion } from '@/shared/motion/tokens'
import { useMotion } from '@/shared/motion/useMotion'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const loginPanel = ref<HTMLElement | null>(null)
const { play, finishAll } = useMotion()

const activeAccount = ref('')
const loginError = ref('')
const failedAccount = ref('')
const accounts = [
  { username: 'engineering', name: '工程部', description: '产品、BOM 与生产流程' },
  { username: 'business', name: '业务部', description: '客户订单与生产计划' },
  { username: 'stamp', name: '冲压部', description: '冲压工艺生产' },
  { username: 'cnc', name: '机加部', description: '机加工艺生产' },
  { username: 'polish', name: '表面处理部', description: '表面处理工艺生产' },
  { username: 'outsource', name: '外协部', description: '蚀字、电镀外协工单' },
  { username: 'qc', name: 'QC部门', description: '质量检验与放行' },
  { username: 'assembly', name: '装配部', description: '装配生产' },
  { username: 'finished', name: '成品部', description: '成品入库与订单发货' },
  { username: 'warehouse', name: '仓库', description: '配件、装配体库存管理' },
] as const

onMounted(() => {
  const panel = loginPanel.value
  if (!panel) return

  panel.querySelectorAll<HTMLElement>('[data-login-motion="reveal"]').forEach((element, index) => {
    play(element, [
      { opacity: 0.5, transform: 'translateY(6px)' },
      { opacity: 1, transform: 'translateY(0)' },
    ], {
      duration: erpMotion.duration.reveal,
      delay: index * erpMotion.stagger,
      easing: erpMotion.easing.enter,
    })
  })

  const scan = panel.querySelector<HTMLElement>('[data-login-motion="scan"]')
  if (scan) {
    play(scan, [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], {
      duration: erpMotion.duration.reveal,
      easing: erpMotion.easing.enter,
    })
  }

  panel.querySelectorAll<HTMLElement>('[data-login-motion="card"]').forEach((element, index) => {
    play(element, [
      { opacity: 0, transform: 'translateY(6px)' },
      { opacity: 1, transform: 'translateY(0)' },
    ], {
      duration: erpMotion.duration.enter,
      delay: Math.min(index * erpMotion.stagger, erpMotion.maxStagger),
      easing: erpMotion.easing.enter,
    })
  })
})

async function loginAs(username: string) {
  finishAll()
  activeAccount.value = username
  loginError.value = ''
  try {
    const user = await authStore.login({ username, password: '1' })
    const defaultPath = getDefaultDashboardPath(user)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : defaultPath
    await router.replace(redirect)
  } catch {
    failedAccount.value = username
    loginError.value = `${accounts.find(account => account.username === username)?.name || username}登录失败，请重试`
  } finally {
    activeAccount.value = ''
  }
}
</script>

<template>
  <main class="login-page">
    <section ref="loginPanel" class="login-panel">
      <div class="login-brand">
        <div class="brand-content" data-login-motion="reveal">
          <div class="brand-mark">ZZ</div>
          <div>
            <h1>ZZ ERP</h1>
            <p>部门操作工作台</p>
          </div>
        </div>
        <span class="login-scan" data-login-motion="scan" aria-hidden="true" />
      </div>

      <div class="account-directory">
        <div class="account-heading" data-login-motion="reveal">
          <h2>选择登录账号</h2>
          <p>点击部门账号直接进入对应工作台</p>
        </div>
        <LoadErrorAlert :message="loginError" title="登录失败" retry-text="重新登录" :loading="authStore.loading" @retry="loginAs(failedAccount)" />
        <div class="account-grid">
          <button
            v-for="account in accounts"
            :key="account.username"
            class="account-card"
            :class="{ 'is-logging-in': activeAccount === account.username }"
            data-login-motion="card"
            type="button"
            :disabled="authStore.loading"
            :aria-busy="activeAccount === account.username"
            @focus="finishAll"
            @click="loginAs(account.username)"
          >
            <span class="account-avatar" aria-hidden="true">{{ account.name.slice(0, 1) }}</span>
            <span class="account-copy">
              <strong>{{ account.name }}</strong>
              <small>{{ account.username }}</small>
              <span>{{ account.description }}</span>
            </span>
            <span v-if="activeAccount === account.username" class="account-state">登录中…</span>
            <span v-else class="account-arrow">进入</span>
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 40px 24px;
  color: var(--erp-text);
  background: var(--erp-bg);
}

.login-panel {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 0;
  width: min(1100px, 100%);
  overflow: hidden;
  border: 1px solid var(--erp-border);
  border-radius: 12px;
  background: var(--erp-surface);
  box-shadow: 0 16px 48px rgb(41 43 39 / 5%);
}

.login-brand {
  position: relative;
  padding: 36px 28px;
  background: var(--erp-inverse);
  color: var(--erp-on-inverse);
}

.brand-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-items: flex-start;
}

.login-scan {
  position: absolute;
  right: 28px;
  bottom: 36px;
  left: 28px;
  height: 2px;
  background: var(--erp-border-strong);
  transform-origin: left center;
  pointer-events: none;
}

.brand-mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid var(--erp-border-strong);
  border-radius: 6px;
  background: transparent;
  color: var(--erp-on-inverse);
  font-size: 18px;
  font-weight: 700;
}

.login-brand h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: .025em;
}

.login-brand p {
  margin: 12px 0 0;
  color: var(--erp-primary-soft);
  font-size: 14px;
  line-height: 1.6;
}

.account-directory {
  min-width: 0;
  padding: 32px;
}

.account-heading {
  margin-bottom: 24px;
}

.account-heading h2 { margin: 0; font-size: 22px; font-weight: 600; line-height: 1.4; }
.account-heading p { margin: 8px 0 0; color: var(--erp-text-muted); font-size: 13px; line-height: 1.6; }
.account-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.account-card {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-width: 0;
  min-height: 94px;
  padding: 15px 14px;
  border: 1px solid var(--erp-border);
  border-radius: 6px;
  background: var(--erp-surface);
  color: var(--erp-text);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 120ms var(--erp-motion-ease-enter), background-color 120ms var(--erp-motion-ease-enter);
}
.account-card:hover:not(:disabled),
.account-card:focus-visible:not(:disabled) { border-color: var(--erp-primary); background: var(--erp-primary-soft); }
.account-card:focus-visible { outline: 2px solid var(--erp-primary); outline-offset: 3px; }
.account-card:active:not(:disabled) { background: var(--erp-surface-sunken); }
.account-card:disabled { cursor: wait; background: var(--erp-surface-sunken); }
.account-card:disabled:not(.is-logging-in) { opacity: .6; }
.account-card.is-logging-in { border-color: var(--erp-primary); background: var(--erp-primary-soft); }
.account-avatar {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border: 1px solid var(--erp-border);
  border-radius: 2px;
  background: var(--erp-surface-sunken);
  color: var(--erp-text);
  font-size: 14px;
  font-weight: 600;
}
.account-copy { display: grid; min-width: 0; gap: 3px; }
.account-copy strong { font-size: 15px; font-weight: 600; line-height: 1.4; }
.account-copy small {
  color: var(--erp-text-muted);
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.account-copy > span {
  margin-top: 3px;
  color: var(--erp-text-muted);
  font-size: 13px;
  line-height: 1.6;
  overflow-wrap: anywhere;
}
.account-arrow, .account-state { color: var(--erp-primary); font-size: 12px; font-weight: 600; line-height: 1.5; white-space: nowrap; }
@media (max-width: 960px) {
  .login-panel { grid-template-columns: 190px minmax(0, 1fr); }
  .account-directory { padding: 24px; }
  .login-brand { padding-right: 24px; }
  .login-scan { right: 24px; }
  .account-card { grid-template-columns: minmax(0, 1fr) auto; }
  .account-avatar { display: none; }
}
@media (max-width: 720px) {
  .login-page { padding: 24px 16px; }
  .login-panel { grid-template-columns: minmax(0, 1fr); }
  .account-directory { padding: 24px; }
  .login-brand { padding: 24px; }
  .brand-content { flex-direction: row; align-items: center; gap: 16px; }
  .login-brand h1 { font-size: 26px; }
  .login-brand p { margin-top: 4px; }
  .login-scan { display: none; }
  .account-heading { margin-bottom: 20px; }
}
@media (max-width: 480px) {
  .login-page { padding: 12px; }
  .account-directory { padding: 24px 18px; }
  .account-grid { grid-template-columns: 1fr; }
  .account-card { grid-template-columns: 32px minmax(0, 1fr) auto; }
  .account-avatar { display: grid; }
}
</style>
