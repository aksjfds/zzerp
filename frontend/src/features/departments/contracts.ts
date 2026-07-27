import type { RouteRecordRaw } from 'vue-router'

export type DepartmentCapability =
  | 'repositories'
  | 'work_orders'
  | 'workers'
  | 'standard_execution'
  | 'purchasing'
  | 'assembly'
  | 'quality'
  | 'special_printing'

export type DepartmentModule = {
  code: string
  name: string
  routePath: string
  routeName: string
  requiredPermission: string
  component: NonNullable<RouteRecordRaw['component']>
  capabilities: readonly DepartmentCapability[]
}
