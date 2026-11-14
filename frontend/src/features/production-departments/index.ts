import { service } from '@/api/request'

export type ProductionDepartment = { code: string; name: string; can_receive: boolean }

export async function queryProductionDepartments(signal?: AbortSignal) {
  const response = await service.get<ProductionDepartment[]>('/production-departments', { signal })
  return response.data
}

export async function queryLoginProductionDepartments(signal?: AbortSignal) {
  const response = await service.get<ProductionDepartment[]>('/production-departments/login-options', { signal })
  return response.data
}
