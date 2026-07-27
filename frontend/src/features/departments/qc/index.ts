import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import type { DepartmentModule } from '../contracts'


export const qcDepartment: DepartmentModule = {
  code: 'qc',
  name: 'QC部门',
  routePath: '/qc',
  routeName: 'qc-department',
  requiredPermission: PRODUCTION_PERMISSIONS.inspect,
  component: () => import('@/features/production/views/QcDepartmentView.vue'),
  capabilities: ['workers', 'quality'],
}
