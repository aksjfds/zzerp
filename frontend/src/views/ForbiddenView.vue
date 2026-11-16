<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDefaultDashboardPath } from '@/permission/defaultRoute'
const router = useRouter()
const auth = useAuthStore()
const home = computed(() => getDefaultDashboardPath(auth.user))
async function switchAccount() {
  try {
    await auth.logout(async () => !await router.push('/login'))
  } catch {
    ElMessage.error('退出未完成，请重试')
  }
}
</script>
<template>
  <main class="forbidden-page">
    <section class="permission-card"><span class="permission-code">403 / 访问权限</span><div class="permission-symbol" aria-hidden="true">↗</div><h1>此页面暂不可访问</h1><div class="permission-actions"><RouterLink v-if="home !== '/forbidden'" :to="home" class="return-link">返回工作台</RouterLink><ElButton @click="switchAccount">切换账号</ElButton></div></section>
  </main>
</template>
<style scoped>
.forbidden-page { display: grid; min-height: calc(100dvh - 64px); padding: 32px 16px; place-items: center; }.permission-card { max-width: 520px; width: 100%; padding: 48px; border: 1px solid var(--erp-border); border-radius: 12px; background: var(--erp-surface); text-align: center; box-shadow: var(--erp-shadow-sm); }.permission-code { color: var(--erp-text-muted); font-size: 12px; }.permission-symbol { display: grid; place-items: center; width: 48px; height: 48px; margin: 24px auto; border-radius: 12px; color: var(--erp-primary); background: var(--erp-primary-soft); font-size: 24px; } h1 { margin: 0 0 16px; font-size: 24px; font-weight: 600; } p { color: var(--erp-text-muted); font-size: 14px; margin: 0; }.permission-actions { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; justify-content: center; margin-top: 32px; }.return-link { display: grid; place-items: center; min-height: 44px; font-size: 14px; }
@media (max-width: 600px) { .permission-card { padding: 32px 24px; } }
</style>
