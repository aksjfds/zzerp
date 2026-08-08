import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const purchasingDepartment: DepartmentModule = {
  code: 'purchasing',
  name: '采购部',
  routePath: '/purchasing',
  routeName: 'purchasing-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/PurchasingDepartmentView.vue'),
  capabilities: [
    'repositories',
    'work_orders',
    'workers',
    'purchasing',
    'production_progress',
  ],
}
