import 'element-plus/dist/index.css'

import { createApp } from 'vue'
import { ElMessage } from 'element-plus'
import { createPinia } from 'pinia'

import App from './App.vue'
import { setupPermission } from './permission'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
setupPermission(app)

const authStore = useAuthStore(pinia)
window.addEventListener('zzerp:unauthorized', () => {
  authStore.clearSession()
  if (router.currentRoute.value.path !== '/login') {
    router.replace('/login')
  }
})
window.addEventListener('zzerp:forbidden', (event) => {
  const detail = event instanceof CustomEvent ? event.detail : undefined
  ElMessage.error(typeof detail === 'string' ? detail : '无权执行此操作')
})

app.mount('#app')
