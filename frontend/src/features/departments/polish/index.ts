import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const polishDepartment: DepartmentModule = {
  code: 'polish',
  name: '表面处理部门',
  routePath: '/polish',
  routeName: 'polish-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/PolishDepartmentView.vue'),
  capabilities: [
    'repositories',
    'work_orders',
    'workers',
    'standard_execution',
    'special_printing',
  ],
}
