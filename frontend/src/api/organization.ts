import { service } from './request'

export type ProcedureOption = {
  id: number
  workshop_id: number
  department_name: string
  department_code: string
  procedure_name: string
  procedure_type: 'standard' | 'purchase_receipt'
  input_mode: 'single' | 'multiple'
}

export type WorkshopRouteOption = {
  id: number
  department_id: number
  department_name: string
  department_code: string
  workshop_name: string
}

export async function queryProcedures() {
  const response = await service.get<ProcedureOption[]>('/procedures')
  return response.data
}

export async function queryWorkshopRoutes() {
  const response = await service.get<WorkshopRouteOption[]>('/workshop-routes')
  return response.data
}
