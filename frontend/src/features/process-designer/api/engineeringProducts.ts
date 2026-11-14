import { service } from '@/api/request'
import type {
  BomItem,
  Appearance,
  CreateProductPayload,
  EngineeringProduct,
  ProcessFlow,
  ProductFields,
  ProductSummary,
} from '../domain/types'

export async function queryProducts(page = 1, pageSize = 50, keyword?: string, signal?: AbortSignal) {
  const response = await service.get<{ data: ProductSummary[]; total: number }>('/products', {
    params: { page, page_size: pageSize, keyword: keyword || undefined },
    signal,
  })
  return response.data
}

export async function queryProduct(productId: number, appearance_id?: number, signal?: AbortSignal) {
  const response = await service.get<{ data: EngineeringProduct }>(`/products/${productId}`, {
    params: appearance_id ? { appearance_id } : undefined,
    signal,
  })
  return response.data.data
}

export async function queryProductAppearances(productId: number, signal?: AbortSignal) {
  const response = await service.get<{ data: Appearance[] }>(`/products/${productId}/appearances`, { signal })
  return response.data.data
}

export async function createProductAppearance(productId: number, expectedRevision: number, appearanceName: string, sourceAppearanceId?: number) {
  return (await service.post<{ data: EngineeringProduct }>(`/products/${productId}/appearances`, {
    expected_revision: expectedRevision, appearance_name: appearanceName, source_appearance_id: sourceAppearanceId,
  })).data.data
}

export async function renameProductAppearance(productId: number, appearanceId: number, expectedRevision: number, appearanceName: string) {
  return (await service.put<{ data: EngineeringProduct }>(`/products/${productId}/appearances/${appearanceId}`, {
    expected_revision: expectedRevision, appearance_name: appearanceName,
  })).data.data
}

export async function createProduct(payload: CreateProductPayload) {
  const response = await service.post<{ data: EngineeringProduct }>('/products', payload)
  return response.data.data
}

export async function updateProductInfo(
  productId: number,
  expectedRevision: number,
  payload: ProductFields,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}`,
    { ...payload, expected_revision: expectedRevision },
  )
  return response.data.data
}

export async function replaceProductBom(
  productId: number,
  expectedRevision: number,
  bomItems: BomItem[],
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/bom`,
    { expected_revision: expectedRevision, bom_items: bomItems },
  )
  return response.data.data
}

export async function updateProductProcessFlow(
  productId: number,
  expectedRevision: number,
  appearanceId: number,
  processFlow: ProcessFlow,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/process-flow`,
    { expected_revision: expectedRevision, appearance_id: appearanceId, process_flow: processFlow },
  )
  return response.data.data
}

export async function saveProductProcessFlowDraft(
  productId: number,
  expectedRevision: number,
  appearanceId: number,
  processFlow: ProcessFlow,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/process-flow/draft`,
    { expected_revision: expectedRevision, appearance_id: appearanceId, process_flow: processFlow },
  )
  return response.data.data
}
