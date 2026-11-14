import { computed, reactive } from 'vue'
import { EMPTY_FLOW, type BomItem, type EngineeringProduct, type ProcessFlow, type ProductFields, type ProductForm } from '../domain/types'

function emptyForm(): ProductForm {
  return {
    appearance_id: null, appearance_name: '', revision: null, customer_id: null, customer_name: '',
    product_name: '', factory_code: '', customer_code: '',
    bom_items: [{ part_name: '', part_no: '', pcs: 1, remark: '' }],
    process_flow: EMPTY_FLOW(), process_flow_is_draft: false,
  }
}

/** Owns the editable document and its saved baselines; it does not perform requests. */
export function useProductDraft() {
  const form = reactive<ProductForm>(emptyForm())
  const capabilities = reactive({ baseEditable: false, appearanceEditable: false })
  const baseline = reactive({ base: '', bom: '', flow: '', appearanceName: '' })
  const baseFields = computed<ProductFields>({
    get: () => ({
      customer_id: form.customer_id, customer_name: form.customer_name,
      product_name: form.product_name, factory_code: form.factory_code, customer_code: form.customer_code,
    }),
    set: value => Object.assign(form, value),
  })
  const baseDirty = computed(() => baseline.base !== JSON.stringify(baseFields.value))
  const bomDirty = computed(() => baseline.bom !== JSON.stringify(form.bom_items))
  const flowDirty = computed(() => baseline.flow !== JSON.stringify(form.process_flow))
  const dirty = computed(() => baseDirty.value || bomDirty.value || flowDirty.value || baseline.appearanceName !== form.appearance_name)

  function markSaved() {
    baseline.appearanceName = form.appearance_name
    baseline.base = JSON.stringify(baseFields.value)
    baseline.bom = JSON.stringify(form.bom_items)
    baseline.flow = JSON.stringify(form.process_flow)
  }

  function applyCapabilities(product: EngineeringProduct) {
    capabilities.baseEditable = product.base_info_editable
    capabilities.appearanceEditable = product.appearance_editable
  }

  function load(product: EngineeringProduct) {
    Object.assign(form, {
      appearance_id: product.appearance_id, appearance_name: product.appearance_name, revision: product.revision,
      customer_id: product.customer_id, customer_name: product.customer_name,
      product_name: product.product_name, factory_code: product.factory_code,
      customer_code: product.customer_code,
      bom_items: product.bom_items.map(item => ({ ...item })),
      process_flow: structuredClone(product.process_flow),
      process_flow_is_draft: product.process_flow_is_draft,
    })
    applyCapabilities(product)
    markSaved()
  }

  function reset() {
    Object.assign(form, emptyForm())
    Object.assign(capabilities, { baseEditable: false, appearanceEditable: false })
    markSaved()
  }

  function normalizedFields(): ProductFields {
    return {
      customer_id: form.customer_id, customer_name: form.customer_name.trim(),
      product_name: form.product_name.trim(), factory_code: form.factory_code.trim(),
      customer_code: form.customer_code.trim(),
    }
  }

  function normalizedBom(): BomItem[] {
    return form.bom_items.map(item => ({
      ...(item.id === undefined ? {} : { id: item.id }),
      part_name: item.part_name.trim(), part_no: item.part_no.trim(),
      pcs: item.pcs, remark: item.remark.trim(),
    }))
  }

  function validateBase(): string | undefined {
    const fields = normalizedFields()
    if (!fields.customer_name || !fields.product_name || !fields.factory_code || !fields.customer_code) {
      return '请填写客户、产品名称、厂编和客编'
    }
    return undefined
  }

  function validateBom(): string | undefined {
    if (!form.bom_items.length) return '请至少添加一条 BOM 明细'
    const numbers = new Set<string>()
    for (const [index, item] of form.bom_items.entries()) {
      if (!item.part_name.trim() || !item.part_no.trim()) return `BOM 第 ${index + 1} 行的配件名称和编号必须填写`
      if (!Number.isInteger(item.pcs) || item.pcs < 1 || item.pcs > 2147483647) {
        return `BOM 第 ${index + 1} 行的用量必须为 1 至 2147483647 的整数`
      }
      const number = item.part_no.trim()
      if (numbers.has(number)) return `BOM 配件编号重复：${number}`
      numbers.add(number)
    }
    return undefined
  }

  function commitBase(product: EngineeringProduct) {
    baseFields.value = {
      customer_id: product.customer_id, customer_name: product.customer_name,
      product_name: product.product_name, factory_code: product.factory_code, customer_code: product.customer_code,
    }
    form.revision = product.revision
    baseline.base = JSON.stringify(baseFields.value)
    applyCapabilities(product)
  }

  function commitBom(product: EngineeringProduct, localFlow: ProcessFlow) {
    const parts = new Map(product.bom_items.map(item => [item.id, item]))
    form.revision = product.revision
    form.bom_items = product.bom_items.map(item => ({ ...item }))
    form.process_flow = {
      ...localFlow,
      nodes: localFlow.nodes.map(node => {
        const part = node.type === 'part' ? parts.get(node.bom_item_id) : undefined
        return part ? { ...node, label: `${part.part_no} · ${part.part_name}` } : node
      }),
    }
    baseline.bom = JSON.stringify(form.bom_items)
    if (product.appearance_id === form.appearance_id) baseline.flow = JSON.stringify(product.process_flow)
    applyCapabilities(product)
  }

  function commitFlow(product: EngineeringProduct) {
    form.revision = product.revision
    form.process_flow = structuredClone(product.process_flow)
    form.process_flow_is_draft = product.process_flow_is_draft
    baseline.flow = JSON.stringify(form.process_flow)
    applyCapabilities(product)
  }

  markSaved()
  return {
    form, baseFields, capabilities, baseDirty, bomDirty, flowDirty, dirty,
    reset, load, normalizedFields, normalizedBom, validateBase, validateBom,
    commitBase, commitBom, commitFlow,
  }
}
