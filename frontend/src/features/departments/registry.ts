import type { RouteRecordRaw } from 'vue-router'
import type { DepartmentCapability, DepartmentModule } from './contracts'
import { assemblyDepartment } from './assembly'
import { cncDepartment } from './cnc'
import { polishDepartment } from './polish'
import { qcDepartment } from './qc'
import { stampDepartment } from './stamp'
import { warehouseDepartment } from './warehouse'


export const departmentModules = [
  stampDepartment,
  cncDepartment,
  polishDepartment,
  qcDepartment,
  assemblyDepartment,
  warehouseDepartment,
] as const satisfies readonly DepartmentModule[]

const moduleByCode = new Map(
  departmentModules.map(module => [module.code, module]),
)

export function getDepartmentModule(code?: string | null) {
  return code ? moduleByCode.get(code) : undefined
}

export function departmentSupports(
  code: string | null | undefined,
  capability: DepartmentCapability,
) {
  return getDepartmentModule(code)?.capabilities.includes(capability) ?? false
}

export const departmentRoutes: RouteRecordRaw[] = departmentModules.map(module => ({
  path: module.routePath,
  name: module.routeName,
  component: module.component,
  meta: {
    requiresAuth: true,
    permissions: [module.requiredPermission],
    departmentCode: module.code,
    departmentCapabilities: module.capabilities,
  },
}))

export const departmentSupportRoutes: RouteRecordRaw[] = departmentModules.flatMap((module) => {
  const routes: RouteRecordRaw[] = []
  if (module.capabilities.includes('workers')) {
    routes.push({
      path: `/production/${module.code}/workers`,
      name: `${module.code}-workers`,
      redirect: {
        path: module.routePath,
        query: { tab: 'workers' },
      },
      meta: {
        requiresAuth: true,
        permissions: [module.requiredPermission],
        departmentCode: module.code,
        requiredDepartmentCapability: 'workers',
      },
    })
  }
  if (module.capabilities.includes('standard_execution')) {
    routes.push({
      path: `/production/${module.code}/tag-prices`,
      name: `${module.code}-tag-prices`,
      redirect: {
        path: module.routePath,
        query: { tab: 'tag-prices' },
      },
      meta: {
        requiresAuth: true,
        permissions: [module.requiredPermission],
        departmentCode: module.code,
        requiredDepartmentCapability: 'standard_execution',
      },
    })
  }
  if (module.capabilities.includes('production_progress')) {
    routes.push({
      path: `/production/${module.code}/progress`,
      name: `${module.code}-production-progress`,
      redirect: {
        path: module.routePath,
        query: { tab: 'progress' },
      },
      meta: {
        requiresAuth: true,
        permissions: [module.requiredPermission],
        departmentCode: module.code,
        requiredDepartmentCapability: 'production_progress',
      },
    })
  }
  return routes
})
