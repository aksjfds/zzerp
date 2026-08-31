import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const stampDepartment: DepartmentModule = {
  code: 'stamp',
  name: '冲压部',
  routePath: '/stamp',
  routeName: 'stamp-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/StampDepartmentView.vue'),
  capabilities: ['production_workbench', 'workers', 'standard_execution', 'production_progress'],
}
