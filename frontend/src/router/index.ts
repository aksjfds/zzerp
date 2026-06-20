import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from '@/permission/guard'
import LoginView from '@/views/LoginView.vue'
import ProductDashboardView from '@/views/ProductDashboardView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/dashboard',
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: ProductDashboardView,
      meta: {
        requiresAuth: true,
        permissions: ['product:view', 'task:view'],
      },
    },
  ],
})

setupRouterGuard(router)

export default router
