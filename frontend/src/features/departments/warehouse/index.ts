import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const warehouseDepartment: DepartmentModule = {
  code: 'warehouse',
  name: '成品部',
  routePath: '/warehouse',
  routeName: 'warehouse-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/WarehouseDepartmentView.vue'),
  capabilities: ['repositories', 'work_orders', 'workers', 'purchasing'],
}
