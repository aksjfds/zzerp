import { service } from './request'

export type WorkshopRouteOption = {
  id: number
  department_id: number
  department_name: string
  department_code: string
  workshop_name: string
}

export async function queryWorkshopRoutes() {
  const response = await service.get<WorkshopRouteOption[]>('/workshop-routes')
  return response.data
}
