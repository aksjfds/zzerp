import type { RouteRecordRaw } from 'vue-router'
import EngineeringProductsView from '@/views/engineering/EngineeringProductsView.vue'
import MasterDataView from '@/views/engineering/MasterDataView.vue'
import ProductStructureView from '@/views/engineering/ProductStructureView.vue'
import CustomerOrdersView from '@/views/business/CustomerOrdersView.vue'
import ProductionPlansView from '@/views/planning/ProductionPlansView.vue'


export const v2Routes: RouteRecordRaw[] = [
  {
    path: '/dashboard/planning',
    name: 'dashboard-planning-plans',
    component: ProductionPlansView,
    meta: {
      department: 'planning',
      requiresAuth: true,
      permissions: ['plan:view', 'plan:edit', 'plan:manage'],
    },
  },
  {
    path: '/dashboard/business',
    name: 'dashboard-business-orders',
    component: CustomerOrdersView,
    meta: {
      department: 'business',
      requiresAuth: true,
      permissions: ['order:view', 'order:edit', 'order:manage'],
    },
  },
  {
    path: '/dashboard/engineering/products/:productId/structure',
    name: 'dashboard-engineering-product-structure',
    component: ProductStructureView,
    meta: {
      department: 'engineering',
      requiresAuth: true,
      permissions: ['product:view', 'product:manage'],
    },
  },
  {
    path: '/dashboard/engineering',
    name: 'dashboard-engineering',
    component: EngineeringProductsView,
    meta: {
      department: 'engineering',
      requiresAuth: true,
      permissions: ['product:view', 'product:manage'],
    },
  },
  {
    path: '/dashboard/master-data',
    name: 'dashboard-master-data',
    component: MasterDataView,
    meta: {
      requiresAuth: true,
      permissions: ['master:manage', 'product:edit'],
    },
  },
]
