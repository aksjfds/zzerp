import { service } from '@/api/request'

export type OrderProduct = {
  id: number
  version: number
  revision: number
  customer_id: number
  customer_name: string
  product_name: string
  factory_code: string
  customer_code: string
  bom_count: number
  order_ready: boolean
  order_ready_reason: string
  created_at: string
  updated_at: string
}

type ProductDetail = Omit<OrderProduct, 'version' | 'bom_count'> & {
  current_version: number
  bom_items: Array<{
    id: number
    product_id: number
    product_version: number
    part_no: string
    part_name: string
    pcs: number
    remark: string
    sort_order: number
  }>
}

export async function queryOrderProducts(customerId: number, keyword?: string) {
  const response = await service.get<{ data: OrderProduct[] }>('/products', {
    params: {
      page: 1,
      page_size: 50,
      customer_id: customerId,
      keyword: keyword || undefined,
    },
  })
  return response.data.data
}

export async function queryOrderProduct(productId: number): Promise<OrderProduct> {
  const response = await service.get<{ data: ProductDetail }>(`/products/${productId}`)
  const product = response.data.data
  return {
    id: product.id,
    version: product.current_version,
    revision: product.revision,
    customer_id: product.customer_id,
    customer_name: product.customer_name,
    product_name: product.product_name,
    factory_code: product.factory_code,
    customer_code: product.customer_code,
    bom_count: product.bom_items.length,
    order_ready: product.order_ready,
    order_ready_reason: product.order_ready_reason,
    created_at: product.created_at,
    updated_at: product.updated_at,
  }
}
