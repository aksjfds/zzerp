<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
.forbidden-page { display: grid; min-height: 100vh; place-items: center; background: var(--erp-bg); }
.forbidden-page section { text-align: center; }
</style>
