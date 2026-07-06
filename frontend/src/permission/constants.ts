export const PRODUCT_PERMISSIONS = {
  view: 'engineering:product:view',
  add: 'engineering:product:add',
  edit: 'engineering:product:edit',
  delete: 'engineering:product:delete',
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
} as const
