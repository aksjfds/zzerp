import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createProduct as createProductApi,
  queryProductRecords,
  queryProducts,
} from '@/api/production'
import type { CreateProductPayload, ProductItem, ProductRecord } from '@/types/production'

export const useProductsStore = defineStore('products', () => {
  const loading = ref(false)
  const products = ref<ProductItem[]>([])
  const records = ref<ProductRecord[]>([])

  const totalQuantity = computed(() =>
    products.value.reduce((total, product) => total + product.quantity, 0),
  )

  async function loadProducts() {
    loading.value = true

    try {
      products.value = await queryProducts()
    } finally {
      loading.value = false
    }
  }

  async function createProduct(payload: CreateProductPayload) {
    await createProductApi(payload)
    await loadProducts()
  }

  async function loadRecords(zzCode: string, product: string) {
    records.value = await queryProductRecords(zzCode, product)
  }

  return {
    createProduct,
    loadProducts,
    loadRecords,
    loading,
    products,
    records,
    totalQuantity,
  }
})
