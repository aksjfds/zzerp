export { queryCustomerOrderProduction } from './api/customerOrders'
export {
  customerOrderStatusLabel,
  customerOrderStatusPresentation,
  customerOrderStatusTagType,
} from './domain/orderStatus'
export { default as CustomerOrdersView } from './views/CustomerOrdersView.vue'
export { default as OrderProgressDetailsView } from './views/OrderProgressDetailsView.vue'
export type {
  CustomerOrderProduction,
  CustomerOrderStatus,
  ProductionPlanStatus,
  ProductionEdgeStat,
  ProductionNodeStat,
} from './domain/types'
