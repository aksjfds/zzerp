import { ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createProduct as createProductApi,
  createProductVersion as createProductVersionApi,
  deleteProduct as deleteProductApi,
  queryProduct,
  queryProducts,
  replaceProductBom,
  updateProductInfo,
  updateProductProcessFlow,
} from '@/features/process-designer/api/engineeringProducts'
import type {
  BomItem,
  EngineeringProduct,
  ProcessFlow,
  ProductFields,
  ProductForm,
  ProductSummary,
} from '@/features/process-designer/domain/types'

export const useEngineeringProductsStore = defineStore('engineeringProducts', () => {
  const products = ref<ProductSummary[]>([])
  const productTotal = ref(0)
  const activeProduct = ref<EngineeringProduct | null>(null)
  const loading = ref(false)
  const saving = ref(false)

  async function loadProducts(page = 1, pageSize = 50) {
    loading.value = true
    try {
      const result = await queryProducts(page, pageSize)
      products.value = result.items
      productTotal.value = result.total
    } finally {
      loading.value = false
    }
  }

  async function loadProduct(productId: number, version?: number) {
    loading.value = true
    try {
      activeProduct.value = await queryProduct(productId, version)
      return activeProduct.value
    } finally {
      loading.value = false
    }
  }

  async function createProduct(form: ProductForm) {
    return withSaving(async () => {
      const product = await createProductApi({
        customer_name: form.customer_name,
        product_name: form.product_name,
        factory_code: form.factory_code,
        customer_code: form.customer_code,
        bom_items: form.bom_items,
      })
      commitActive(product)
      return product
    })
  }

  async function saveProductInfo(productId: number, revision: number, fields: ProductFields) {
    return withSaving(async () => {
      const product = await updateProductInfo(productId, revision, fields)
      commitActive(product)
      return product
    })
  }

  async function saveProductBom(productId: number, revision: number, bomItems: BomItem[]) {
    return withSaving(async () => {
      const product = await replaceProductBom(productId, revision, bomItems)
      commitActive(product)
      return product
    })
  }

  async function saveProcessFlow(productId: number, revision: number, flow: ProcessFlow) {
    return withSaving(async () => {
      const product = await updateProductProcessFlow(productId, revision, flow)
      commitActive(product)
      return product
    })
  }

  async function removeProduct(productId: number, expectedRevision: number) {
    await deleteProductApi(productId, expectedRevision)
    if (activeProduct.value?.id === productId) activeProduct.value = null
    products.value = products.value.filter((product) => product.id !== productId)
    productTotal.value = Math.max(productTotal.value - 1, 0)
  }

  async function createVersion(productId: number, expectedRevision: number) {
    return withSaving(async () => {
      const product = await createProductVersionApi(productId, expectedRevision)
      commitActive(product)
      return product
    })
  }

  function commitActive(product: EngineeringProduct) {
    activeProduct.value = product
    const summary: ProductSummary = {
      id: product.id,
      version: product.version,
      revision: product.revision,
      customer_name: product.customer_name,
      product_name: product.product_name,
      factory_code: product.factory_code,
      customer_code: product.customer_code,
      bom_count: product.bom_items.length,
      created_at: product.created_at,
      updated_at: product.updated_at,
    }
    products.value = [summary, ...products.value.filter((item) => item.id !== product.id)]
  }

  async function withSaving<T>(action: () => Promise<T>) {
    saving.value = true
    try {
      return await action()
    } finally {
      saving.value = false
    }
  }

  return {
    activeProduct,
    createProduct,
    createVersion,
    loadProduct,
    loadProducts,
    loading,
    products,
    productTotal,
    removeProduct,
    saveProcessFlow,
    saveProductBom,
    saveProductInfo,
    saving,
  }
})
