import { createRouter, createWebHistory } from 'vue-router'
import { setupRouterGuard } from '@/permission/guard'
import LoginView from '@/views/LoginView.vue'
import EngineeringProductsView from '@/features/process-designer/views/EngineeringProductsView.vue'
import EngineeringProductEditorView from '@/features/process-designer/views/EngineeringProductEditorView.vue'
import ForbiddenView from '@/views/ForbiddenView.vue'
import { PRODUCT_PERMISSIONS } from '@/permission/constants'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/products' },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/forbidden', name: 'forbidden', component: ForbiddenView, meta: { requiresAuth: true } },
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
