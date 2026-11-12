export const PRODUCT_PERMISSIONS = {
  view: 'engineering:product:view',
  add: 'engineering:product:add',
  edit: 'engineering:product:edit',
} as const

export const DEPARTMENT_WORK_ORDER_VIEW = 'department:work-order:view'
export const DEPARTMENT_WORK_ORDER_OPERATE = 'department:work-order:operate'

export const PLAN_PERMISSIONS = {
  view: 'plan:view',
  add: 'plan:add',
  edit: 'plan:edit',
  confirm: 'plan:confirm',
  cancel: 'plan:cancel',
} as const
