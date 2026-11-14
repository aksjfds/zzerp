<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/features/identity'

const router = useRouter()
const authStore = useAuthStore()

async function logout() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <main class="forbidden-page">
    <section>
      <ElEmpty description="当前账号无权访问该页面" />
      <ElButton type="primary" @click="logout">切换账号</ElButton>
    </section>
  </main>
</template>

<style scoped>
.forbidden-page { display: grid; min-height: 100vh; padding: 24px; place-items: center; background: var(--md-surface); }
.forbidden-page section { width: min(480px, 100%); padding: 32px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); color: var(--erp-text); text-align: center; }
</style>
