import { computed, reactive, ref } from 'vue'
import {
  EMPTY_FLOW,
  type BomItem,
  type EngineeringProduct,
  type ProductFields,
  type ProductForm,
} from '../domain/types'

export function useProductEditorForm() {
  const form = reactive<ProductForm>({
    version: null,
    customer_name: '',
    product_name: '',
    factory_code: '',
    customer_code: '',
    bom_items: [{ part_name: '', part_no: '', pcs: 1, remark: '' }],
    process_flow: EMPTY_FLOW(),
  })
  const baseSnapshot = ref('')
  const bomSnapshot = ref('')
  const flowSnapshot = ref('')
  const serializeBase = () => JSON.stringify({
    customer_name: form.customer_name,
    product_name: form.product_name,
    factory_code: form.factory_code,
    customer_code: form.customer_code,
  })
  const baseDirty = computed(() => baseSnapshot.value !== serializeBase())
  const bomDirty = computed(() => bomSnapshot.value !== JSON.stringify(form.bom_items))
  const flowDirty = computed(() => flowSnapshot.value !== JSON.stringify(form.process_flow))
  const hasUnsavedChanges = computed(() => baseDirty.value || bomDirty.value || flowDirty.value)

  function markSaved(sections: Array<'base' | 'bom' | 'flow'>) {
    if (sections.includes('base')) baseSnapshot.value = serializeBase()
    if (sections.includes('bom')) bomSnapshot.value = JSON.stringify(form.bom_items)
    if (sections.includes('flow')) flowSnapshot.value = JSON.stringify(form.process_flow)
  }

  function normalizedFields(): ProductFields {
    return {
      customer_name: form.customer_name.trim(),
      product_name: form.product_name.trim(),
      factory_code: form.factory_code.trim(),
      customer_code: form.customer_code.trim(),
    }
  }

  function normalizedBom(): BomItem[] {
    return form.bom_items.map((item) => ({
      ...item,
      part_name: item.part_name.trim(),
      part_no: item.part_no.trim(),
      pcs: item.pcs,
      remark: item.remark.trim(),
    }))
  }

  function validateBom(): string | null {
    if (!form.bom_items.length) return '请至少添加一条 BOM 明细'
    const partNumbers = new Set<string>()
    for (const [index, item] of form.bom_items.entries()) {
      if (
        !item.part_name.trim()
        || !item.part_no.trim()
        || !Number.isInteger(item.pcs)
        || item.pcs < 1
      ) {
        return `BOM 第 ${index + 1} 行的配件名称、配件编号和用量必须填写`
      }
      const partNo = item.part_no.trim()
      if (partNumbers.has(partNo)) return `BOM 配件编号重复：${partNo}`
      partNumbers.add(partNo)
    }
    return null
  }

  function applyProduct(product: EngineeringProduct) {
    Object.assign(form, {
      version: product.version,
      customer_name: product.customer_name,
      product_name: product.product_name,
      factory_code: product.factory_code,
      customer_code: product.customer_code,
      bom_items: product.bom_items.map((item) => ({ ...item })),
      process_flow: product.process_flow,
    })
  }

  return {
    applyProduct,
    baseDirty,
    baseSnapshot,
    bomDirty,
    bomSnapshot,
    flowDirty,
    flowSnapshot,
    form,
    hasUnsavedChanges,
    markSaved,
    normalizedBom,
    normalizedFields,
    validateBom,
  }
}
