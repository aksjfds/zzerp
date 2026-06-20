import 'element-plus/dist/index.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { setupPermission } from './permission'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
setupPermission(app)

app.mount('#app')
