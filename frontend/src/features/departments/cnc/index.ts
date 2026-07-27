import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const cncDepartment: DepartmentModule = {
  code: 'cnc',
  name: '机加部',
  routePath: '/cnc',
  routeName: 'cnc-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/CncDepartmentView.vue'),
  capabilities: ['repositories', 'work_orders', 'workers', 'standard_execution'],
}
