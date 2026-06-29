import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from '@/permission/guard'
import LoginView from '@/views/LoginView.vue'
import ProductDashboardView from '@/views/ProductDashboardView.vue'
import PolishDashboardView from '@/views/departments/PolishDashboardView.vue'
import QcDashboardView from '@/views/departments/QcDashboardView.vue'

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
    },
    {
      path: '/dashboard/polish',
      name: 'dashboard-polish',
      component: PolishDashboardView,
      meta: {
        department: 'polish',
        requiresAuth: true,
        permissions: ['task:view'],
      },
    },
    {
      path: '/dashboard/qc',
      name: 'dashboard-qc',
      component: QcDashboardView,
      meta: {
        department: 'qc',
        requiresAuth: true,
        permissions: ['task:view'],
      },
    },
  ],
})

setupRouterGuard(router)

export default router
