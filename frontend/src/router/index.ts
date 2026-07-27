import { createRouter, createWebHistory } from 'vue-router'
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
    {
      path: '/stamp', name: 'stamp-department',
      component: () => import('@/features/production/views/StampDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/cnc', name: 'cnc-department',
      component: () => import('@/features/production/views/CncDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/polish', name: 'polish-department',
      component: () => import('@/features/production/views/PolishDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/qc', name: 'qc-department',
      component: () => import('@/features/production/views/QcDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.inspect] },
    },
    {
      path: '/assembly', name: 'assembly-department',
      component: () => import('@/features/production/views/AssemblyDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/warehouse', name: 'warehouse-department',
      component: () => import('@/features/production/views/WarehouseDepartmentView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/production/:departmentCode/tag-prices',
      name: 'procedure-tag-prices',
      component: () => import('@/features/production/views/ProcedureTagPriceView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/production/:departmentCode/workers',
      name: 'department-workers',
      component: () => import('@/features/production/views/DepartmentWorkersView.vue'),
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
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
      component: () => import('@/features/customer-orders/views/CustomerOrdersView.vue'),
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
