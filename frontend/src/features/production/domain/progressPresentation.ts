import type { ProductionPlanStatus } from '@/features/customer-orders'
import type { ProductionProgressProcedureCard } from './productionProgress'
export { workOrderStatusLabels } from './workOrderStatus'

export const progressCardStatusLabels: Record<ProductionProgressProcedureCard['status'], string> = {
  not_arrived: '未到货',
  ready: '待开工',
  processing: '生产中',
  pending_qc: '待检',
  completed: '已完成',
  exception: '存在异常',
}

export const progressCardStatusTypes: Record<
  ProductionProgressProcedureCard['status'],
  'info' | 'primary' | 'warning' | 'success' | 'danger'
> = {
  not_arrived: 'info',
  ready: 'primary',
  processing: 'warning',
  pending_qc: 'warning',
  completed: 'success',
  exception: 'danger',
}

export const planStatusLabels: Record<ProductionPlanStatus, string> = {
  draft: '草稿',
  confirmed: '已确认',
  cancelled: '已取消',
  completed: '已完成',
}

export function exceptionQuantity(card: ProductionProgressProcedureCard) {
  return card.rework_quantity + card.scrap_quantity + card.lost_quantity
}

export function progressSegments(card: ProductionProgressProcedureCard) {
  let remaining = Math.max(card.task_quantity, 0)
  const take = (quantity: number) => {
    const result = Math.min(Math.max(quantity, 0), remaining)
    remaining -= result
    return result
  }
  const completed = take(Math.min(card.completed_quantity, card.task_quantity))
  const exception = take(exceptionQuantity(card))
  const submitted = take(card.pending_qc_quantity)
  const processing = take(card.processing_quantity)
  return { completed, exception, submitted, processing }
}

export function segmentProgressWidth(
  card: ProductionProgressProcedureCard,
  segment: keyof ReturnType<typeof progressSegments>,
) {
  if (card.task_quantity <= 0) return '0%'
  const quantity = progressSegments(card)[segment]
  return `${Math.min(Math.max(quantity / card.task_quantity * 100, 0), 100)}%`
}

export function currentProgressQuantity(card: ProductionProgressProcedureCard) {
  return Object.values(progressSegments(card)).reduce((total, quantity) => total + quantity, 0)
}

export function displayWorkshopName(name: string) {
  return name.replace(/车间$/, '') || '—'
}
