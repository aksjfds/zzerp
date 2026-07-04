import { service } from '@/api/request'
import type {
  BomItem,
  CreateProductPayload,
  EngineeringProduct,
  ProcessFlow,
  ProductFields,
  ProductSummary,
} from '../domain/types'

export async function queryProducts() {
  const response = await service.get<{ data: ProductSummary[] }>('/products')
  return response.data.data
}

export async function queryProduct(productId: number) {
  const response = await service.get<{ data: EngineeringProduct }>(`/products/${productId}`)
  return response.data.data
}

export async function createProduct(payload: CreateProductPayload) {
  const response = await service.post<{ data: EngineeringProduct }>('/products', payload)
  return response.data.data
}

export async function updateProductInfo(
  productId: number,
  expectedVersion: number,
  payload: ProductFields,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}`,
    { ...payload, expected_version: expectedVersion },
  )
  return response.data.data
}

export async function replaceProductBom(
  productId: number,
  expectedVersion: number,
  bomItems: BomItem[],
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/bom`,
    { expected_version: expectedVersion, bom_items: bomItems },
  )
  return response.data.data
}

export async function updateProductProcessFlow(
  productId: number,
  expectedVersion: number,
  processFlow: ProcessFlow,
) {
  const response = await service.put<{ data: EngineeringProduct }>(
    `/products/${productId}/process-flow`,
    { expected_version: expectedVersion, process_flow: processFlow },
  )
  return response.data.data
}

export async function deleteProduct(productId: number, expectedVersion: number) {
  await service.delete(`/products/${productId}`, {
    params: { expected_version: expectedVersion },
  })
}
