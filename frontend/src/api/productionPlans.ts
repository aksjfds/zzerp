import { service } from './request'
import type {
  PlanItemInput,
  PlanMaterialAdjustmentInput,
  ProductionPlan,
  ProductionPlanPreview,
  ProductionPlanStatus,
} from '@/types/planning'

export async function queryV2ProductionPlans(status?: ProductionPlanStatus) {
  const response = await service.get<ProductionPlan[]>('/v2/production-plans', {
    params: { status },
  })
  return response.data
}

export async function previewV2ProductionPlan(
  customerOrderId: number,
  items: PlanItemInput[],
) {
  const response = await service.post<ProductionPlanPreview>(
    '/v2/production-plans/preview',
    { customerOrderId, items },
  )
  return response.data
}

export async function previewV2ProductionPlanUpdate(
  planId: number,
  items: PlanItemInput[],
) {
  const response = await service.post<ProductionPlanPreview>(
    `/v2/production-plans/${planId}/preview`,
    { items },
  )
  return response.data
}

export type ProductionPlanWritePayload = {
  customerOrderId?: number
  startDate: string
  completionDate: string
  items: PlanItemInput[]
  materialAdjustments: PlanMaterialAdjustmentInput[]
}

export async function createV2ProductionPlan(payload: ProductionPlanWritePayload) {
  const response = await service.post<ProductionPlan>('/v2/production-plans', payload)
  return response.data
}

export async function updateV2ProductionPlan(
  planId: number,
  payload: Omit<ProductionPlanWritePayload, 'customerOrderId'>,
) {
  const response = await service.put<ProductionPlan>(
    `/v2/production-plans/${planId}`,
    payload,
  )
  return response.data
}

export async function releaseV2ProductionPlan(planId: number) {
  const response = await service.post<ProductionPlan>(
    `/v2/production-plans/${planId}/release`,
  )
  return response.data
}

export async function cancelV2ProductionPlan(planId: number) {
  const response = await service.post<ProductionPlan>(
    `/v2/production-plans/${planId}/cancel`,
  )
  return response.data
}
