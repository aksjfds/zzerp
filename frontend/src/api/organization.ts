import { service } from './request'

export type ProcedureOption = {
  id: number
  workshop_id: number
  procedure_name: string
}

export async function queryProcedures() {
  const response = await service.get<ProcedureOption[]>('/procedures')
  return response.data
}
