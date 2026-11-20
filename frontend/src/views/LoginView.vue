<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { queryLoginProductionDepartments, type ProductionDepartment } from '@/features/production-departments'
import { getApiErrorDetail } from '@/api/request'
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
const departments = ref<ProductionDepartment[]>([])
const departmentLoading = ref(false)
const departmentError = ref('')
let active = true
let requestRevision = 0
const accounts = computed(() => [
  { key: 'engineering', username: 'engineering', name: '工程部', description: '产品、BOM 与生产流程', path: '' },
  { key: 'business', username: 'business', name: '业务部', description: '生产计划管理', path: '' },
  ...departments.value.filter(department => department.code !== 'purchase').map(department => ({
    key: `department:${department.code}`, username: department.code, name: department.name,
    description: '本部门工单、到料与出料',
    path: `/departments/${encodeURIComponent(department.code)}/work-orders`,
  })),
])

const accountSearch = ref('')
const accountGroups = computed(() => {
  const keyword = accountSearch.value.trim().toLowerCase()
  return [
    { key: 'management', title: '业务与工程', description: '维护生产依据，安排客户订单', items: accounts.value.slice(0, 2) },
    { key: 'production', title: '生产部门', description: '进入所属部门，处理工单与物料交接', items: accounts.value.slice(2) },
  ].map(group => ({ ...group, items: group.items.filter(account => `${account.name} ${account.username}`.toLowerCase().includes(keyword)) }))
})

async function loadDepartments() {
  const current = ++requestRevision
  departmentLoading.value = true
  departmentError.value = ''
  try {
    const result = await queryLoginProductionDepartments()
    if (active && current === requestRevision) departments.value = result
  } catch (cause) {
    if (active && current === requestRevision) departmentError.value = getApiErrorDetail(cause)?.message || '生产部门入口加载失败'
  } finally { if (active && current === requestRevision) departmentLoading.value = false }
}

onBeforeUnmount(() => { active = false; requestRevision += 1 })

onMounted(() => {
  void loadDepartments()
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

async function loginAs(key: string) {
  const account = accounts.value.find(item => item.key === key)
  if (!account || authStore.loading) return
  finishAll()
  activeAccount.value = key
  loginError.value = ''
  try {
    const user = await authStore.login({ username: account.username, password: '1' })
    if (!active) return
    const defaultPath = getDefaultDashboardPath(user)
    const redirect = user.department_code ? defaultPath
      : account.path || (typeof route.query.redirect === 'string' ? route.query.redirect : defaultPath)
    await router.replace(redirect)
  } catch {
    if (!active) return
    failedAccount.value = key
    loginError.value = `${account.name}登录失败，请重试`
  } finally {
    if (active) activeAccount.value = ''
  }
}
</script>

<template>
  <main class="login-page">
    <div class="login-masthead"><span class="brand-mark">ZZ</span><strong>ZZ ERP</strong><span>制造业务工作台</span></div>
    <section ref="loginPanel" class="login-panel">
      <div class="login-introduction" data-login-motion="reveal">
        <span class="intro-label">清晰协同 · 有序生产</span>
        <h1>从产品资料，<br>到每一道工序。</h1>
        <p>将工程、订单与部门生产连接起来，<br class="desktop-break">让信息有依据，让流转可追溯。</p>
        <ol class="workflow-preview" aria-label="业务协作流程">
          <li><span>01</span><div><strong>建立产品工程</strong><small>产品资料、BOM 与工艺路线</small></div></li>
          <li><span>02</span><div><strong>安排生产计划</strong><small>客户订单与产品生产数量</small></div></li>
          <li><span>03</span><div><strong>协同部门生产</strong><small>工单、物料交接与生产流水</small></div></li>
        </ol>
        <span class="intro-rule" data-login-motion="scan" aria-hidden="true" />
        <p class="intro-footnote">统一的工作空间，明确的部门职责。</p>
      </div>
      <div class="account-directory">
        <div class="account-heading" data-login-motion="reveal"><span>欢迎使用</span><h2>选择你的工作入口</h2><p>以对应岗位进入，生产账号仅访问本部门。</p></div>
        <ElInput v-model="accountSearch" class="account-search" clearable placeholder="查找部门或账号" aria-label="查找部门或账号" />
        <LoadErrorAlert :message="loginError" title="登录失败" retry-text="重新登录" :loading="authStore.loading" @retry="loginAs(failedAccount)" />
        <LoadErrorAlert :message="departmentError" title="部门入口加载失败" :loading="departmentLoading" @retry="loadDepartments" />
        <section v-for="group in accountGroups" :key="group.key" class="account-group" :aria-label="group.title">
          <div class="group-heading"><h3>{{ group.title }}</h3><span>{{ group.description }}</span></div>
          <div class="account-grid" :aria-busy="group.key === 'production' && departmentLoading">
            <button v-for="account in group.items" :key="account.key" class="account-card" :class="{ 'is-logging-in': activeAccount === account.key }" data-login-motion="card" type="button" :disabled="authStore.loading" :aria-busy="activeAccount === account.key" @focus="finishAll" @click="loginAs(account.key)">
              <span class="account-avatar" aria-hidden="true">{{ account.name.slice(0, 1) }}</span>
              <span class="account-copy"><strong>{{ account.name }}</strong><small>{{ account.path ? '部门工单' : account.username }}</small></span>
              <span class="account-arrow">{{ activeAccount === account.key ? '登录中…' : '→' }}</span>
            </button>
          </div>
          <ElSkeleton v-if="group.key === 'production' && departmentLoading && !group.items.length" :rows="3" animated />
          <p v-else-if="!group.items.length && !departmentError" class="empty-accounts">{{ accountSearch ? '未找到匹配入口，请调整关键词' : '暂无可用部门入口' }}</p>
        </section>
      </div>
    </section>
    <footer class="login-footer">ZZ ERP <span>工程 · 计划 · 生产</span></footer>
  </main>
</template>

<style scoped>
.login-page { min-height: 100dvh; padding: 32px 48px 24px; max-width: 1440px; margin: auto; }
.login-masthead { display: flex; align-items: center; gap: 12px; font-size: 18px; }
.login-masthead > span:last-child { border-left: 1px solid var(--erp-border-strong); padding-left: 16px; margin-left: 4px; color: var(--erp-text-muted); font-size: 12px; }
.brand-mark { display: grid; place-items: center; width: 40px; height: 40px; background: var(--erp-primary); color: var(--erp-on-primary); border-radius: 12px; font-size: 16px; font-weight: 700; }
.login-panel { display: grid; grid-template-columns: minmax(280px, .85fr) minmax(0, 1.5fr); max-width: 1120px; margin: 64px auto 48px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); box-shadow: var(--erp-shadow-sm); overflow: hidden; }
.login-introduction { padding: 48px 32px; background: var(--erp-primary-soft); }
.intro-label { color: var(--erp-primary); font-size: 12px; font-weight: 500; letter-spacing: .08em; }
h1 { margin: 24px 0 16px; font-size: 36px; line-height: 1.3; font-weight: 600; letter-spacing: -.035em; }
.login-introduction > p { color: var(--erp-text-muted); font-size: 14px; line-height: 1.8; }
.workflow-preview { display: grid; gap: 28px; list-style: none; padding: 0; margin: 48px 0; }
.workflow-preview li { display: flex; align-items: center; gap: 16px; }
.workflow-preview li > span { display: grid; place-items: center; width: 36px; height: 36px; border: 1px solid var(--el-color-primary-light-8); border-radius: 8px; background: var(--erp-surface); color: var(--erp-primary); font-size: 12px; font-weight: 600; }
.workflow-preview strong { display: block; font-size: 14px; font-weight: 500; }.workflow-preview small { display: block; color: var(--erp-text-muted); font-size: 12px; margin-top: 4px; }
.intro-rule { display: block; height: 1px; background: var(--el-color-primary-light-8); transform-origin: left; }
.login-introduction .intro-footnote { margin-top: 20px; font-size: 12px; }
.account-directory { min-width: 0; padding: 40px; }
.account-heading > span { color: var(--erp-text-muted); font-size: 12px; }
h2 { margin: 8px 0; font-size: 24px; font-weight: 600; letter-spacing: -.025em; }
.account-heading p { color: var(--erp-text-muted); font-size: 14px; margin: 0; }
.account-search { margin: 24px 0 8px; }
.account-group { margin-top: 24px; }.group-heading { margin-bottom: 12px; }.group-heading h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; }.group-heading > span { color: var(--erp-text-muted); font-size: 12px; }
.account-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.account-card { display: flex; align-items: center; gap: 12px; min-height: 80px; padding: 16px; min-width: 0; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); color: var(--erp-text); cursor: pointer; text-align: left; }
.account-avatar { display: grid; place-items: center; flex-shrink: 0; width: 40px; height: 40px; border-radius: 12px; background: var(--erp-primary-soft); color: var(--erp-primary); font-size: 14px; font-weight: 600; transition: background-color 150ms ease-out, color 150ms ease-out, transform 150ms ease-out; }
.account-copy { min-width: 0; }.account-copy strong { display: block; font-size: 14px; font-weight: 500; }.account-copy small { display: block; margin-top: 4px; font-size: 12px; color: var(--erp-text-muted); overflow-wrap: anywhere; }
.account-arrow { margin-left: auto; font-size: 14px; color: var(--erp-primary); }
.account-card:disabled { cursor: wait; opacity: .65; }.account-card.is-logging-in { border-color: var(--erp-primary); background: var(--erp-primary-soft); }
.empty-accounts { font-size: 14px; color: var(--erp-text-muted); padding-block: 16px; }
.login-footer { display: flex; gap: 16px; justify-content: center; color: var(--erp-text-muted); font-size: 12px; }.login-footer span { padding-left: 16px; border-left: 1px solid var(--erp-border); }
@media (hover: hover) and (pointer: fine) { .account-card:not(:disabled):hover { border-color: var(--erp-primary); box-shadow: var(--erp-shadow-md); transform: translateY(-2px); } .account-card:not(:disabled):hover .account-avatar { background: var(--erp-primary); color: var(--erp-on-primary); transform: scale(1.1); } .account-card:not(:disabled):active { transform: scale(.98); } }
@media (max-width: 1100px) { .login-page { padding: 24px; }.login-panel { margin-top: 40px; }.account-directory { padding: 32px 24px; }.login-introduction { padding: 40px 24px; }.account-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .login-page { padding: 24px 16px; }.login-panel { grid-template-columns: 1fr; margin: 32px 0; }.login-introduction { padding: 24px; } h1 { font-size: 30px; margin-top: 16px; }.workflow-preview { display: none; }.intro-rule, .intro-footnote, .desktop-break { display: none; }.account-directory { padding: 24px; }.account-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.group-heading > span { display: none; } }
@media (max-width: 480px) { .account-grid { grid-template-columns: 1fr; }.login-masthead > span:last-child { display: none; } }
@media (prefers-reduced-motion: reduce) { .account-card:hover, .account-card:active, .account-card:hover .account-avatar { transform: none !important; } }
</style>
