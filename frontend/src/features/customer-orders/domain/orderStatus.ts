import type { CustomerOrderStatus } from './types'

type OrderStatusPresentation = {
  label: string
  tagType: 'primary' | 'success' | 'warning' | 'info' | 'danger'
}

export const customerOrderStatusPresentation: Record<
  CustomerOrderStatus,
  OrderStatusPresentation
> = {
  draft: { label: '草稿', tagType: 'info' },
  confirmed: { label: '已确认', tagType: 'primary' },
  planned: { label: '生产中', tagType: 'warning' },
  cancelled: { label: '已取消', tagType: 'danger' },
  closed: { label: '已完成', tagType: 'success' },
}

export function customerOrderStatusLabel(status: CustomerOrderStatus) {
  return customerOrderStatusPresentation[status].label
}

export function customerOrderStatusTagType(status: CustomerOrderStatus) {
  return customerOrderStatusPresentation[status].tagType
}
