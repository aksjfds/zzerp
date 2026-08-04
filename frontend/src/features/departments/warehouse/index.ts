import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const warehouseDepartment: DepartmentModule = {
  code: 'warehouse',
  name: '仓库',
  routePath: '/warehouse',
  routeName: 'warehouse-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/inventory/views/InventoryDepartmentView.vue'),
  capabilities: ['inventory'],
}
