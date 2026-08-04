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
  | 'production_progress'
  | 'inventory'
  | 'finished_goods'

export type DepartmentModule = {
  code: string
  name: string
  routePath: string
  routeName: string
  requiredPermission: string
  component: NonNullable<RouteRecordRaw['component']>
  capabilities: readonly DepartmentCapability[]
}
