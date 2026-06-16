import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import ProductionPlanView from '@/views/ProductionPlanView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/production-plan',
      name: 'production-plan',
      component: ProductionPlanView,
    },
  ],
})

export default router
