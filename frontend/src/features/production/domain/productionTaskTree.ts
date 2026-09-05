import type {
  DepartmentProductionProgressItem,
  ProductionTaskProcessingStatus,
  ProductionTaskProcessingStatusCode,
} from './productionProgress'

export type ProductionTaskParentRow = {
  row_key: string
  row_type: 'task'
  task: DepartmentProductionProgressItem
  overview_statuses: ProductionTaskOverviewStatus[]
}

export type ProductionTaskStatusRow = {
  row_key: string
  row_type: 'status'
  task: DepartmentProductionProgressItem
  status: ProductionTaskProcessingStatus
  is_last_child: boolean
}

export type ProductionTaskTreeRow =
  | ProductionTaskParentRow
  | ProductionTaskStatusRow

export const productionTaskStatusPresentation: Record<
  ProductionTaskProcessingStatusCode,
  { type: 'info' | 'primary' | 'warning' | 'success' | 'danger' }
> = {
  not_started: { type: 'info' },
  processing: { type: 'warning' },
  submitted_qc: { type: 'primary' },
  rework: { type: 'danger' },
  completed: { type: 'success' },
  exception: { type: 'danger' },
  department_completed: { type: 'success' },
}

type ProductionTaskOverviewStatusKey =
  | 'plan_unconfirmed'
  | 'waiting_material'
  | 'ready'
  | 'processing'
  | 'submitted_qc'
  | 'rework'
  | 'exception'
  | 'department_completed'

export type ProductionTaskOverviewStatus = {
  key: ProductionTaskOverviewStatusKey
  label: string
  type: 'info' | 'primary' | 'warning' | 'success' | 'danger'
  quantity: number | null
}

export function productionTaskOverviewStatuses(
  item: DepartmentProductionProgressItem,
): ProductionTaskOverviewStatus[] {
  if (item.plan_status === 'draft') {
    return [{ key: 'plan_unconfirmed', label: '计划未确认', type: 'info', quantity: null }]
  }

  const quantities = new Map<ProductionTaskOverviewStatusKey, number>()
  const addQuantity = (key: ProductionTaskOverviewStatusKey, quantity: number) => {
    quantities.set(key, (quantities.get(key) || 0) + quantity)
  }

  for (const status of item.processing_statuses) {
    if (status.status === 'exception') {
      addQuantity('exception', status.quantity)
    } else if (status.status === 'not_started') {
      const key = status.action === 'none' ? 'waiting_material' : 'ready'
      addQuantity(key, status.quantity)
    } else if (status.status === 'completed') {
      addQuantity('ready', status.quantity)
    } else if (status.status !== 'department_completed') {
      addQuantity(status.status, status.quantity)
    }
  }
  if (item.completed_quantity > 0) addQuantity('department_completed', item.completed_quantity)

  const presentation: Array<Omit<ProductionTaskOverviewStatus, 'quantity'>> = [
    { key: 'waiting_material', label: '等待物料', type: 'info' },
    { key: 'ready', label: '可开工', type: 'primary' },
    { key: 'processing', label: '加工中', type: 'warning' },
    { key: 'submitted_qc', label: '已送检', type: 'primary' },
    { key: 'rework', label: '返工中', type: 'danger' },
    { key: 'exception', label: '异常', type: 'danger' },
    { key: 'department_completed', label: '本部门完成', type: 'success' },
  ]
  return presentation.flatMap(status => {
    const quantity = quantities.get(status.key) || 0
    return quantity > 0 ? [{ ...status, quantity }] : []
  })
}

function combineExceptionStatuses(
  statuses: ProductionTaskProcessingStatus[],
): ProductionTaskProcessingStatus {
  const workOrderQuantities = new Map<number, number>()
  const batchQuantities = new Map<number, number>()
  const procedureNames = new Set<string>()
  for (const status of statuses) {
    status.procedure_names.forEach(name => procedureNames.add(name))
    status.related_work_orders.forEach(item => {
      workOrderQuantities.set(
        item.work_order_id,
        (workOrderQuantities.get(item.work_order_id) || 0) + item.quantity,
      )
    })
    status.related_batches.forEach(item => {
      batchQuantities.set(
        item.batch_id,
        (batchQuantities.get(item.batch_id) || 0) + item.quantity,
      )
    })
  }
  return {
    status: 'exception',
    label: procedureNames.size ? `${[...procedureNames].join('、')} · 异常` : '异常',
    action: 'view_work_orders',
    quantity: statuses.reduce((sum, status) => sum + status.quantity, 0),
    procedure_names: [...procedureNames],
    repository_ids: [],
    related_work_orders: [...workOrderQuantities].map(([work_order_id, quantity]) => ({
      work_order_id,
      quantity,
    })),
    related_batches: [...batchQuantities].map(([batch_id, quantity]) => ({
      batch_id,
      quantity,
    })),
    creation_mode: null,
  }
}

export function buildProductionTaskRows(
  items: DepartmentProductionProgressItem[],
): ProductionTaskTreeRow[] {
  return items.flatMap(item => {
    const taskKey = [
      item.production_plan_item_id,
      item.flow_node_id,
    ].join(':')
    const parent: ProductionTaskParentRow = {
      row_key: `task:${taskKey}`,
      row_type: 'task',
      task: item,
      overview_statuses: productionTaskOverviewStatuses(item),
    }
    const regularStatuses = item.processing_statuses.filter(
      status => status.status !== 'exception',
    )
    const exceptionStatuses = item.processing_statuses.filter(
      status => status.status === 'exception',
    )
    const visibleStatuses = exceptionStatuses.length
      ? [...regularStatuses, combineExceptionStatuses(exceptionStatuses)]
      : regularStatuses
    const statusRows = visibleStatuses.map((status, index): ProductionTaskStatusRow => ({
      row_key: [
        'status',
        taskKey,
        status.status,
        status.label,
        status.creation_mode || '',
        status.repository_ids.join(','),
        status.related_work_orders.map(item => item.work_order_id).join(','),
        status.related_batches.map(item => item.batch_id).join(','),
      ].join(':'),
      row_type: 'status',
      task: item,
      status,
      is_last_child: index === visibleStatuses.length - 1,
    }))
    return [parent, ...statusRows]
  })
}

export function displayWorkshopName(name: string) {
  return name.replace(/车间$/, '') || '—'
}
