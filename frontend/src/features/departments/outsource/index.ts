import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const outsourceDepartment: DepartmentModule = {
  code: 'outsource',
  name: '外协部',
  routePath: '/outsource',
  routeName: 'outsource-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/OutsourceDepartmentView.vue'),
  capabilities: [
    'repositories',
    'work_orders',
    'workers',
    'standard_execution',
    'production_progress',
  ],
}
