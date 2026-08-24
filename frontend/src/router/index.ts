import { createRouter, createWebHistory } from 'vue-router'
import { departmentRoutes, departmentSupportRoutes } from '@/features/departments'
import { setupRouterGuard } from '@/permission/guard'
import { ORDER_PERMISSIONS, PRODUCT_PERMISSIONS, PRODUCTION_PERMISSIONS } from '@/permission/constants'

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
    ...departmentRoutes,
    ...departmentSupportRoutes,
    {
      path: '/admin',
      name: 'admin-dashboard',
      component: () => import('@/features/admin/views/AdminDashboardView.vue'),
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view, PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/pmc',
      name: 'pmc-dashboard',
      component: () => import('@/features/admin/views/AdminDashboardView.vue'),
      props: { mode: 'pmc' },
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view, PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/business/orders',
      name: 'customer-orders',
      component: () => import('@/features/customer-orders/views/BusinessDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view] },
    },
    {
      path: '/business/orders/new',
      name: 'customer-order-create',
      component: () => import('@/features/customer-orders/views/CustomerOrderEditorView.vue'),
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.add] },
    },
    {
      path: '/business/orders/:orderId(\\d+)',
      name: 'customer-order-edit',
      component: () => import('@/features/customer-orders/views/CustomerOrderEditorView.vue'),
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view] },
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
