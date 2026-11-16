<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { PRODUCT_PERMISSIONS, PLAN_PERMISSIONS, DEPARTMENT_WORK_ORDER_VIEW } from '@/permission/constants'
import { getDefaultDashboardPath } from '@/permission/defaultRoute'
import AppIcon from '@/shared/icons/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const leaving = ref(false)
const links = computed(() => {
  const department = auth.user?.department_code
  if (department) return auth.hasPermission([PLAN_PERMISSIONS.view, DEPARTMENT_WORK_ORDER_VIEW])
    ? [{ path: `/departments/${encodeURIComponent(department)}/work-orders`, label: '部门生产', icon: 'progress' as const }] : []
  return [
    ...(auth.hasPermission(PRODUCT_PERMISSIONS.view) ? [{ path: '/products', label: '产品工程', icon: 'products' as const }] : []),
    ...(auth.hasPermission(PLAN_PERMISSIONS.view) ? [
      { path: '/production-plans', label: '生产计划', icon: 'plans' as const },
      { path: '/department-work-orders', label: '生产进度', icon: 'progress' as const },
    ] : []),
  ]
})
const current = computed(() => links.value.find(link => route.path === link.path || route.path.startsWith(`${link.path}/`)))
async function logout() {
  if (leaving.value) return
  leaving.value = true
  try {
    // Navigate first so the editor's unsaved-changes guard can cancel leaving.
    await auth.logout(async () => !await router.push('/login'))
  } catch {
    ElMessage.error('退出未完成，请重试')
  } finally { leaving.value = false }
}
</script>

<template>
  <div class="workspace">
    <a class="skip-link" href="#workspace-content">跳转到主要内容</a>
    <aside class="workspace-sidebar">
      <RouterLink :to="getDefaultDashboardPath(auth.user)" class="workspace-brand" aria-label="ZZ ERP 工作台首页">
        <span class="brand-symbol">ZZ</span><span>ZZ ERP</span>
      </RouterLink>
      <div class="nav-label">工作空间</div>
      <nav aria-label="主要导航">
        <RouterLink v-for="link in links" :key="link.path" :to="link.path" class="nav-item" :class="{ 'is-current': current?.path === link.path }" :aria-current="current?.path === link.path ? 'page' : undefined">
          <AppIcon :name="link.icon" /><span>{{ link.label }}</span><AppIcon v-if="current?.path === link.path" name="arrow" class="nav-arrow" />
        </RouterLink>
      </nav>
    </aside>
    <div class="workspace-body">
      <header class="workspace-topbar">
        <div class="workspace-context"><span>工作台</span><AppIcon name="arrow" /><strong>{{ current?.label || '访问权限' }}</strong></div>
        <div class="workspace-account"><span class="user-avatar" aria-hidden="true">{{ auth.user?.name?.slice(0, 1) || '用' }}</span><span class="user-name">{{ auth.user?.name || auth.user?.username }}</span><ElButton text :loading="leaving" @click="logout"><AppIcon name="logout" /><span>退出</span></ElButton></div>
      </header>
      <div id="workspace-content" class="workspace-content" tabindex="-1"><slot /></div>
    </div>
  </div>
</template>

<style scoped>
.workspace { display: grid; grid-template-columns: 224px minmax(0, 1fr); min-height: 100dvh; }
.workspace-sidebar { position: sticky; top: 0; height: 100dvh; padding: 28px 16px 24px; display: flex; flex-direction: column; border-right: 1px solid var(--erp-border); background: var(--erp-surface); }
.workspace-brand { min-height: 44px; display: flex; gap: 12px; align-items: center; padding: 0 12px; color: var(--erp-text); font-size: 19px; font-weight: 700; letter-spacing: -.02em; }
.brand-symbol { display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px; background: var(--erp-primary); color: var(--erp-on-primary); font-size: 16px; }
.nav-label { margin: 48px 16px 12px; font-size: 11px; font-weight: 600; color: var(--erp-text-muted); letter-spacing: .12em; }
nav { display: grid; gap: 8px; }
.nav-item { display: flex; min-height: 48px; align-items: center; gap: 12px; padding: 12px 16px; border-radius: 8px; color: var(--erp-text-secondary); font-size: 14px; font-weight: 500; }
.nav-item.is-current { background: var(--erp-primary-soft); color: var(--erp-primary); }
.nav-arrow { width: 14px; height: 14px; margin-left: auto; }
.workspace-body { min-width: 0; }
.workspace-topbar { display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 64px; padding: 8px 32px; border-bottom: 1px solid var(--erp-border); background: var(--erp-surface); }
.workspace-context, .workspace-account { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.workspace-context { color: var(--erp-text-muted); }
.workspace-context svg { width: 12px; height: 12px; }
.workspace-context strong { color: var(--erp-text-secondary); font-weight: 500; }
.user-avatar { display: grid; place-items: center; width: 32px; height: 32px; border: 1px solid var(--erp-border); border-radius: 50%; color: var(--erp-primary); background: var(--erp-primary-soft); font-size: 12px; font-weight: 600; }
.workspace-account :deep(.el-button > span) { gap: 8px; }
.skip-link { position: fixed; top: -100px; left: 16px; z-index: 5000; padding: 12px 24px; border-radius: 8px; background: var(--erp-surface); }
.skip-link:focus { top: 12px; }
@media (hover: hover) and (pointer: fine) { .nav-item:hover { background: var(--erp-surface-muted); color: var(--erp-primary); } .nav-item.is-current:hover { background: var(--erp-primary-soft); } }
@media (max-width: 1000px) { .workspace { grid-template-columns: 192px minmax(0, 1fr); } .workspace-topbar { padding-inline: 24px; } }
@media (max-width: 760px) {
  .workspace { display: block; }
  .workspace-sidebar { position: static; height: auto; padding: 16px 16px 0; border-right: 0; border-bottom: 1px solid var(--erp-border); }
  .workspace-brand { padding: 0; font-size: 18px; }
  .nav-label, .nav-arrow { display: none; }
  nav { display: flex; overflow-x: auto; gap: 8px; margin-top: 16px; padding-bottom: 12px; }
  .nav-item { flex-shrink: 0; min-height: 44px; padding: 10px 12px; }
  .workspace-topbar { min-height: 56px; padding: 8px 16px; }
  .workspace-account { gap: 8px; } .user-name { max-width: 100px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
@media (max-width: 400px) { .workspace-context > span, .workspace-context > svg, .user-avatar { display: none; } }
</style>
