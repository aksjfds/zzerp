import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from '@/permission/guard'
import LoginView from '@/views/LoginView.vue'
import EngineeringProductsView from '@/features/process-designer/views/EngineeringProductsView.vue'
import EngineeringProductEditorView from '@/features/process-designer/views/EngineeringProductEditorView.vue'
import ForbiddenView from '@/views/ForbiddenView.vue'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'
import { ORDER_PERMISSIONS, PRODUCTION_PERMISSIONS } from '@/permission/constants'
import CustomerOrdersView from '@/features/customer-orders/views/CustomerOrdersView.vue'
import CustomerOrderEditorView from '@/features/customer-orders/views/CustomerOrderEditorView.vue'
import StampDepartmentView from '@/features/production/views/StampDepartmentView.vue'
import PolishDepartmentView from '@/features/production/views/PolishDepartmentView.vue'
import QcDepartmentView from '@/features/production/views/QcDepartmentView.vue'
import AssemblyDepartmentView from '@/features/production/views/AssemblyDepartmentView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/forbidden', name: 'forbidden', component: ForbiddenView, meta: { requiresAuth: true } },
    {
      path: '/stamp', name: 'stamp-department', component: StampDepartmentView,
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/polish', name: 'polish-department', component: PolishDepartmentView,
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/qc', name: 'qc-department', component: QcDepartmentView,
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/assembly', name: 'assembly-department', component: AssemblyDepartmentView,
      meta: { requiresAuth: true, permissions: [PRODUCTION_PERMISSIONS.view] },
    },
    {
      path: '/business/orders',
      name: 'customer-orders',
      component: CustomerOrdersView,
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view] },
    },
    {
      path: '/business/orders/new',
      name: 'customer-order-create',
      component: CustomerOrderEditorView,
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.add] },
    },
    {
      path: '/business/orders/:orderId(\\d+)',
      name: 'customer-order-edit',
      component: CustomerOrderEditorView,
      meta: { requiresAuth: true, permissions: [ORDER_PERMISSIONS.view] },
    },
    {
      path: '/products',
      name: 'engineering-products',
      component: EngineeringProductsView,
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.view] },
    },
    {
      path: '/products/new',
      name: 'engineering-product-create',
      component: EngineeringProductEditorView,
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.add] },
    },
    {
      path: '/products/:productId(\\d+)',
      name: 'engineering-product-edit',
      component: EngineeringProductEditorView,
      meta: { requiresAuth: true, permissions: [PRODUCT_PERMISSIONS.edit] },
    },
  ],
})

setupRouterGuard(router)

export default router
