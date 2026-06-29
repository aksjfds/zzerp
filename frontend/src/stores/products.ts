import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  createProduct as createProductApi,
  queryProductDepartmentProgress,
  queryProducts,
} from '@/api/production'
import type {
  CreateProductPayload,
  Department,
  ProductDepartmentProgress,
  ProductItem,
} from '@/types/production'

export const useProductsStore = defineStore('products', () => {
  const loading = ref(false)
  const products = ref<ProductItem[]>([])
  const departmentProgress = ref<ProductDepartmentProgress | null>(null)
  const progressLoading = ref(false)

  const totalQuantity = computed(() =>
    products.value.reduce((total, product) => total + product.quantity, 0),
  )

  async function loadProducts(department?: Department) {
    loading.value = true

    try {
      products.value = await queryProducts(department)
    } finally {
      loading.value = false
    }
  }

  async function createProduct(payload: CreateProductPayload) {
    await createProductApi(payload)
    await loadProducts()
  }

  async function loadDepartmentProgress(productId: number, department: Department) {
    progressLoading.value = true
    departmentProgress.value = null
    try {
      departmentProgress.value = await queryProductDepartmentProgress(productId, department)
    } finally {
      progressLoading.value = false
    }
  }

  return {
    createProduct,
    departmentProgress,
    loadDepartmentProgress,
    loadProducts,
    loading,
    products,
    progressLoading,
    totalQuantity,
  }
})
