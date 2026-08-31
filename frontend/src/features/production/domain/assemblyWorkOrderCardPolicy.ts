import type { WorkOrderCardPolicy } from './workOrderCardPolicy'
import {
  commonStatusType,
  commonWorkOrderActions,
  commonWorkOrderStatusText,
} from './workOrderCardPolicy'

export const assemblyWorkOrderCardPolicy: WorkOrderCardPolicy = {
  metrics: item => [
    { label: '对应产品', value: item.quantity },
    { label: '装配体数量', value: item.output_quantity },
    { label: '合格', value: item.qualified_output_quantity },
    ...(item.pending_qc_quantity ? [{ label: '质检中', value: item.pending_qc_quantity }] : []),
    ...(item.scrap_quantity ? [{ label: '报废', value: item.scrap_quantity }] : []),
    ...(item.lost_quantity ? [{ label: '遗失', value: item.lost_quantity }] : []),
  ],
  statusText: commonWorkOrderStatusText,
  statusType: commonStatusType,
  ...commonWorkOrderActions,
}
