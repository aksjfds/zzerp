import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import {
  commonStatusType,
  commonWorkOrderActions,
  commonWorkOrderStatusText,
} from './workOrderCardPolicy'

export const productionWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metrics: item => [
    { label: '工单数量', value: item.quantity },
    { label: '合格', value: item.qualified_quantity },
    ...(item.pending_qc_quantity ? [{ label: '质检中', value: item.pending_qc_quantity }] : []),
    ...(item.rework_quantity ? [{ label: '返工', value: item.rework_quantity }] : []),
    ...(item.scrap_quantity ? [{ label: '报废', value: item.scrap_quantity }] : []),
    ...(item.lost_quantity ? [{ label: '遗失', value: item.lost_quantity }] : []),
  ],
  statusText: commonWorkOrderStatusText,
  statusType: commonStatusType,
  ...commonWorkOrderActions,
}
