import { service } from './request'
import type {
  DepartmentSummary,
  EngineeringProduct,
  MaterialInput,
  MaterialSummary,
  MaterialRouteVersion,
  ProductBomVersion,
  ProductCustomerCodeInput,
  ProductInput,
  ProductionStructure,
  SemiFinishedVersion,
  SurfaceTreatmentSummary,
  WorkshopSummary,
} from '@/types/engineering'

export async function queryV2Departments() {
  const response = await service.get<DepartmentSummary[]>('/v2/master-data/departments')
  return response.data
}

export type BomVersionPayload = {
  items: Array<{ materialId: number; quantity: number }>
}

export type SemiFinishedVersionPayload = {
  quantityPerFinished: number
  inputs: Array<{ inputMaterialId: number; quantity: number }>
}

export type MaterialRoutePayload = {
  steps: Array<{
    stepType: 'internal' | 'external_surface'
    departmentId?: number
    workshopId?: number
  }>
}

export async function queryV2MaterialRoutes(productId: number) {
  const response = await service.get<MaterialRouteVersion[]>(
    `/v2/engineering/products/${productId}/material-routes`,
  )
  return response.data
}

export async function createV2MaterialRoute(
  materialId: number,
  payload: MaterialRoutePayload,
) {
  const response = await service.post<MaterialRouteVersion>(
    `/v2/engineering/materials/${materialId}/route-versions`,
    payload,
  )
  return response.data
}

export async function updateV2MaterialRoute(
  versionId: number,
  payload: MaterialRoutePayload,
) {
  const response = await service.put<MaterialRouteVersion>(
    `/v2/engineering/route-versions/${versionId}`,
    payload,
  )
  return response.data
}

export async function publishV2MaterialRoute(versionId: number) {
  const response = await service.post<MaterialRouteVersion>(
    `/v2/engineering/route-versions/${versionId}/publish`,
  )
  return response.data
}

export async function deleteV2MaterialRoute(versionId: number) {
  await service.delete(`/v2/engineering/route-versions/${versionId}`)
}

export async function queryV2BomVersions(productId: number) {
  const response = await service.get<ProductBomVersion[]>(
    `/v2/engineering/products/${productId}/bom-versions`,
  )
  return response.data
}

export async function createV2BomVersion(productId: number, payload: BomVersionPayload) {
  const response = await service.post<ProductBomVersion>(
    `/v2/engineering/products/${productId}/bom-versions`,
    payload,
  )
  return response.data
}

export async function updateV2BomVersion(versionId: number, payload: BomVersionPayload) {
  const response = await service.put<ProductBomVersion>(
    `/v2/engineering/bom-versions/${versionId}`,
    payload,
  )
  return response.data
}

export async function publishV2BomVersion(versionId: number) {
  const response = await service.post<ProductBomVersion>(
    `/v2/engineering/bom-versions/${versionId}/publish`,
  )
  return response.data
}

export async function deleteV2BomVersion(versionId: number) {
  await service.delete(`/v2/engineering/bom-versions/${versionId}`)
}

export async function queryV2SemiFinishedVersions(productId: number) {
  const response = await service.get<SemiFinishedVersion[]>(
    `/v2/engineering/products/${productId}/semi-finished-versions`,
  )
  return response.data
}

export async function createV2SemiFinishedVersion(
  materialId: number,
  payload: SemiFinishedVersionPayload,
) {
  const response = await service.post<SemiFinishedVersion>(
    `/v2/engineering/materials/${materialId}/semi-finished-versions`,
    payload,
  )
  return response.data
}

export async function updateV2SemiFinishedVersion(
  versionId: number,
  payload: SemiFinishedVersionPayload,
) {
  const response = await service.put<SemiFinishedVersion>(
    `/v2/engineering/semi-finished-versions/${versionId}`,
    payload,
  )
  return response.data
}

export async function publishV2SemiFinishedVersion(versionId: number) {
  const response = await service.post<SemiFinishedVersion>(
    `/v2/engineering/semi-finished-versions/${versionId}/publish`,
  )
  return response.data
}

export async function deleteV2SemiFinishedVersion(versionId: number) {
  await service.delete(`/v2/engineering/semi-finished-versions/${versionId}`)
}

export async function queryV2ProductionStructure(productId: number) {
  const response = await service.get<ProductionStructure>(
    `/v2/engineering/products/${productId}/production-structure`,
  )
  return response.data
}

export async function queryV2Workshops(departmentId?: number) {
  const response = await service.get<WorkshopSummary[]>('/v2/master-data/workshops', {
    params: { department_id: departmentId },
  })
  return response.data
}

export async function createV2Workshop(payload: {
  departmentId: number
  workshopCode: string
  workshopName: string
}) {
  const response = await service.post<WorkshopSummary>('/v2/master-data/workshops', payload)
  return response.data
}

export async function updateV2Workshop(
  workshopId: number,
  payload: { workshopName?: string; active?: boolean },
) {
  const response = await service.patch<WorkshopSummary>(
    `/v2/master-data/workshops/${workshopId}`,
    payload,
  )
  return response.data
}

export async function queryV2SurfaceTreatments(customerName?: string) {
  const response = await service.get<SurfaceTreatmentSummary[]>(
    '/v2/master-data/surface-treatments',
    { params: { customer_name: customerName } },
  )
  return response.data
}

export async function createV2SurfaceTreatment(
  customerName: string,
  treatmentName: string,
) {
  const response = await service.post<SurfaceTreatmentSummary>(
    '/v2/master-data/surface-treatments',
    { customerName, treatmentName },
  )
  return response.data
}

export async function updateV2SurfaceTreatment(
  treatmentId: number,
  payload: { treatmentName?: string; active?: boolean },
) {
  const response = await service.patch<SurfaceTreatmentSummary>(
    `/v2/master-data/surface-treatments/${treatmentId}`,
    payload,
  )
  return response.data
}

export async function queryV2Products(keyword?: string) {
  const response = await service.get<EngineeringProduct[]>('/v2/engineering/products', {
    params: { keyword },
  })
  return response.data
}

export async function queryV2Product(productId: number) {
  const response = await service.get<EngineeringProduct>(
    `/v2/engineering/products/${productId}`,
  )
  return response.data
}

export async function createV2Product(payload: ProductInput) {
  const response = await service.post<EngineeringProduct>('/v2/engineering/products', payload)
  return response.data
}

export async function updateV2ProductName(productId: number, productName: string) {
  const response = await service.patch<EngineeringProduct>(
    `/v2/engineering/products/${productId}`,
    { productName },
  )
  return response.data
}

export async function publishV2Product(productId: number) {
  const response = await service.post<EngineeringProduct>(
    `/v2/engineering/products/${productId}/publish`,
  )
  return response.data
}

export async function deactivateV2Product(productId: number) {
  const response = await service.post<EngineeringProduct>(
    `/v2/engineering/products/${productId}/deactivate`,
  )
  return response.data
}

export async function addV2ProductCustomerCode(
  productId: number,
  payload: ProductCustomerCodeInput,
) {
  const response = await service.post<EngineeringProduct>(
    `/v2/engineering/products/${productId}/customer-codes`,
    payload,
  )
  return response.data
}

export async function updateV2ProductCustomerCode(
  customerCodeId: number,
  payload: { treatmentIds?: number[]; active?: boolean },
) {
  const response = await service.patch<EngineeringProduct>(
    `/v2/engineering/customer-codes/${customerCodeId}`,
    payload,
  )
  return response.data
}

export async function addV2Material(productId: number, payload: MaterialInput) {
  const response = await service.post<MaterialSummary>(
    `/v2/engineering/products/${productId}/materials`,
    payload,
  )
  return response.data
}

export async function updateV2Material(
  materialId: number,
  payload: Partial<MaterialInput> & {
    active?: boolean
  },
) {
  const response = await service.patch<MaterialSummary>(
    `/v2/engineering/materials/${materialId}`,
    payload,
  )
  return response.data
}
