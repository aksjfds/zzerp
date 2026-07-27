import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const assemblyDepartment: DepartmentModule = {
  code: 'assembly',
  name: '装配部',
  routePath: '/assembly',
  routeName: 'assembly-department',
  requiredPermission: PRODUCTION_PERMISSIONS.view,
  component: () => import('@/features/production/views/AssemblyDepartmentView.vue'),
  capabilities: ['repositories', 'work_orders', 'workers', 'assembly'],
}
