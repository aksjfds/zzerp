import { service } from '@/api/request'

export type ProductionDepartment = { code: string; name: string; can_receive: boolean }

export async function queryProductionDepartments() {
  const response = await service.get<ProductionDepartment[]>('/production-departments')
  return response.data
}

export async function queryLoginProductionDepartments() {
  const response = await service.get<ProductionDepartment[]>('/production-departments/login-options')
  return response.data
}
