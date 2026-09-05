import type {
  CustomerOrderMaterialPosition,
  CustomerOrderMaterialProgress,
  CustomerOrderMaterialStatus,
  CustomerOrderProgressDetail,
} from './types'

export type OrderProgressProductRow = {
  row_key: string
  row_type: 'product'
  product: CustomerOrderProgressDetail
  is_last_material: false
}

export type OrderProgressMaterialRow = {
  row_key: string
  row_type: 'material'
  product: CustomerOrderProgressDetail
  material: CustomerOrderMaterialProgress
  is_last_material: boolean
  is_last_position: false
}

export type OrderProgressPositionRow = {
  row_key: string
  row_type: 'position'
  product: CustomerOrderProgressDetail
  material: CustomerOrderMaterialProgress
  position: {
    flow_node_id: string
    route_order: number
    position_name: string
    department_name: string
    statuses: CustomerOrderMaterialPosition[]
  }
  is_last_material: boolean
  is_last_position: boolean
}

export type OrderProgressTreeRow =
  | OrderProgressProductRow
  | OrderProgressMaterialRow
  | OrderProgressPositionRow

export const orderProgressStatusPresentation: Record<
  CustomerOrderMaterialStatus,
  { type: 'info' | 'primary' | 'warning' | 'success' | 'danger' }
> = {
  plan_unconfirmed: { type: 'info' },
  plan_cancelled: { type: 'info' },
  not_arrived: { type: 'info' },
  not_started: { type: 'primary' },
  processing: { type: 'warning' },
  submitted_qc: { type: 'primary' },
  rework: { type: 'danger' },
  completed: { type: 'success' },
  exception: { type: 'danger' },
  department_completed: { type: 'success' },
  assembly_consumed: { type: 'primary' },
  stored: { type: 'success' },
  transferred: { type: 'success' },
}

const materialTypeOrder: Record<CustomerOrderMaterialProgress['item_type'], number> = {
  part: 0,
  assembly: 1,
}

function groupMaterialPositions(positions: CustomerOrderMaterialPosition[]) {
  const grouped = new Map<string, OrderProgressPositionRow['position']>()
  for (const position of positions) {
    const key = [
      position.flow_node_id,
      position.position_name,
      position.department_name,
    ].join(':')
    const existing = grouped.get(key)
    if (existing) {
      existing.statuses.push(position)
      continue
    }
    grouped.set(key, {
      flow_node_id: position.flow_node_id,
      route_order: position.route_order,
      position_name: position.position_name,
      department_name: position.department_name,
      statuses: [position],
    })
  }
  return [...grouped.values()]
}

export function buildOrderProgressRows(
  products: CustomerOrderProgressDetail[],
): OrderProgressTreeRow[] {
  return products.flatMap(product => {
    const materials = [...product.materials].sort(
      (left, right) => materialTypeOrder[left.item_type] - materialTypeOrder[right.item_type],
    )
    const rows: OrderProgressTreeRow[] = [{
      row_key: `product:${product.customer_order_item_id}`,
      row_type: 'product',
      product,
      is_last_material: false,
    }]
    materials.forEach((material, materialIndex) => {
      const isLastMaterial = materialIndex === materials.length - 1
      rows.push({
        row_key: `material:${material.production_plan_item_id}`,
        row_type: 'material',
        product,
        material,
        is_last_material: isLastMaterial,
        is_last_position: false,
      })
      const positions = groupMaterialPositions(material.positions)
      positions.forEach((position, positionIndex) => {
        rows.push({
          row_key: [
            'position',
            material.production_plan_item_id,
            position.flow_node_id,
            position.position_name,
            positionIndex,
          ].join(':'),
          row_type: 'position',
          product,
          material,
          position,
          is_last_material: isLastMaterial,
          is_last_position: positionIndex === positions.length - 1,
        })
      })
    })
    return rows
  })
}
