import type {
  ProductionOverviewRow,
  ProductionOverviewSummary,
  WorkOrder,
} from './types'

export function aggregateProductionOverviewRows(rows: ProductionOverviewRow[]) {
  const quantities = new Map<string, number>()
  rows.forEach((row) => {
    if (row.quantity <= 0) return
    quantities.set(row.name, (quantities.get(row.name) || 0) + row.quantity)
  })
  return [...quantities.entries()].map(([name, quantity]) => ({ name, quantity }))
}

export function workOrderProductionOverview(
  workOrders: WorkOrder[],
  pendingQuantity: number,
): ProductionOverviewSummary {
  const activeOrders = workOrders.filter(item => item.status !== 'cancelled')
  return {
    pendingQuantity,
    processingRows: aggregateProductionOverviewRows(activeOrders.map(item => ({
      name: item.work_order_name,
      quantity: item.processing_quantity,
    }))),
    pendingQcRows: aggregateProductionOverviewRows(activeOrders.map(item => ({
      name: item.work_order_name,
      quantity: item.pending_qc_quantity,
    }))),
    completedRows: aggregateProductionOverviewRows(activeOrders.map(item => ({
      name: item.work_order_name,
      quantity: item.qualified_quantity,
    }))),
  }
}
