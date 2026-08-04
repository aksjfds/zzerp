import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const finishedDepartment: DepartmentModule = {
  code: 'finished',
  name: '成品部',
  routePath: '/finished',
  routeName: 'finished-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/FinishedDepartmentView.vue'),
  capabilities: ['finished_goods', 'inventory'],
}
