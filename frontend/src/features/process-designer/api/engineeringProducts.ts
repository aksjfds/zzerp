import { service } from '@/api/request'
import type {
  BomItem,
  CreateProductPayload,
  EngineeringProduct,
  ProcessFlow,
  ProductFields,
  ProductSummary,
} from '../domain/types'

export async function queryProducts(page = 1, pageSize = 50, keyword?: string) {
  const response = await service.get<{ data: ProductSummary[]; total: number }>('/products', {
    params: { page, page_size: pageSize, keyword: keyword || undefined },
  })
  return { items: response.data.data, total: response.data.total }
}

export async function queryProduct(productId: number, version?: number) {
  const response = await service.get<{ data: EngineeringProduct }>(`/products/${productId}`, {
    params: version ? { version } : undefined,
  })
  return response.data.data
}

export async function queryProductVersions(productId: number) {
  const response = await service.get<{ data: number[] }>(`/products/${productId}/versions`)
  return response.data.data
}

export async function createProductVersion(
  productId: number,
  expectedRevision: number,
  sourceVersion?: number,
) {
  const response = await service.post<{ data: EngineeringProduct }>(
    `/products/${productId}/versions`,
    undefined,
    { params: { expected_revision: expectedRevision, source_version: sourceVersion } },
  )
  return response.data.data
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
  productVersion: number,
  bomItems: BomItem[],
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/bom`,
    { expected_revision: expectedRevision, product_version: productVersion, bom_items: bomItems },
  )
  return response.data.data
}

export async function updateProductProcessFlow(
  productId: number,
  expectedRevision: number,
  productVersion: number,
  processFlow: ProcessFlow,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/process-flow`,
    { expected_revision: expectedRevision, product_version: productVersion, process_flow: processFlow },
  )
  return response.data.data
}

export async function saveProductProcessFlowDraft(
  productId: number,
  expectedRevision: number,
  productVersion: number,
  processFlow: ProcessFlow,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/process-flow/draft`,
    { expected_revision: expectedRevision, product_version: productVersion, process_flow: processFlow },
  )
  return response.data.data
}

export async function deleteProduct(productId: number, expectedRevision: number) {
  await service.delete(`/products/${productId}`, {
    params: { expected_revision: expectedRevision },
  })
}

export async function deleteProductVersion(
  productId: number,
  productVersion: number,
  expectedRevision: number,
) {
  const response = await service.delete<{ data: EngineeringProduct | null }>(
    `/products/${productId}/versions/${productVersion}`,
    { params: { expected_revision: expectedRevision } },
  )
  return response.data.data
}
