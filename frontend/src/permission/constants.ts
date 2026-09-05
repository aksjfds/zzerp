export const PRODUCT_PERMISSIONS = {
  view: 'engineering:product:view',
  add: 'engineering:product:add',
  edit: 'engineering:product:edit',
} as const

export const ORDER_PERMISSIONS = {
  view: 'order:view',
  add: 'order:add',
  edit: 'order:edit',
  confirm: 'order:confirm',
  cancel: 'order:cancel',
} as const

export const PRODUCTION_PERMISSIONS = {
  view: 'production:view',
  manage: 'production:manage',
  inspect: 'qc:inspect',
} as const

export const SUPPLIER_PROCESSING_PERMISSIONS = {
  view: 'supplier_processing:view',
  create: 'supplier_processing:create',
} as const
