import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from '@/permission/guard'
import { DEPARTMENT_WORK_ORDER_VIEW, PLAN_PERMISSIONS, PRODUCT_PERMISSIONS } from '@/permission/constants'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/forbidden',
      name: 'forbidden',
      component: () => import('@/views/ForbiddenView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/production-plans',
      name: 'production-plans',
      component: () => import('@/features/production-plans/views/ProductionPlansView.vue'),
      meta: { requiresAuth: true, permissions: [PLAN_PERMISSIONS.view] },
    },
    {
      path: '/department-work-orders',
      name: 'department-work-orders',
      component: () => import('@/features/production-plans/views/DepartmentWorkOrdersView.vue'),
      meta: { requiresAuth: true, permissions: [PLAN_PERMISSIONS.view] },
    },
    {
      path: '/departments/:departmentCode/work-orders',
      name: 'department-production',
      component: () => import('@/features/production-plans/views/DepartmentWorkOrdersView.vue'),
      meta: { requiresAuth: true, permissions: [PLAN_PERMISSIONS.view, DEPARTMENT_WORK_ORDER_VIEW] },
    },
    {
      path: '/products',
      name: 'engineering-products',
      component: () => import('@/features/process-designer/views/EngineeringProductsView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.view] },
    },
    {
      path: '/products/new',
      name: 'engineering-product-create',
      component: () => import('@/features/process-designer/views/EngineeringProductEditorView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.add] },
    },
    {
      path: '/products/:productId(\\d+)',
      name: 'engineering-product-edit',
      component: () => import('@/features/process-designer/views/EngineeringProductEditorView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.view] },
    },
  ],
})

setupRouterGuard(router)

export default router
