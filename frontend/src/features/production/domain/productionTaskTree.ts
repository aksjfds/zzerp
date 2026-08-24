import type { DepartmentProductionProgressItem } from './productionProgress'

export type ProductionTaskTreeRow = DepartmentProductionProgressItem & {
  row_key: string
  is_material: boolean
  has_materials: boolean
  process_rowspan: number
}

const ASSEMBLY_MERGED_COLUMNS = new Set([
  'processing_workshop',
  'task_quantity',
  'completed_quantity',
  'remark',
])

export function buildProductionTaskRows(
  items: DepartmentProductionProgressItem[],
  departmentCode: string,
): ProductionTaskTreeRow[] {
  return items.flatMap((item) => {
    const parent: ProductionTaskTreeRow = {
      ...item,
      row_key: `task:${item.production_plan_item_id}:${item.flow_node_id || item.processing_workshop}`,
      is_material: false,
      has_materials: item.material_arrivals.length > 0,
      process_rowspan: departmentCode === 'assembly' ? item.material_arrivals.length + 1 : 1,
    }
    const materials = item.material_arrivals.map((material, index): ProductionTaskTreeRow => ({
      production_plan_item_id: item.production_plan_item_id,
      production_item_id: null,
      flow_node_id: null,
      part_no: material.material_no,
      part_name: material.material_name,
      processing_workshop: '',
      task_quantity: material.task_quantity,
      arrived_quantity: material.arrived_quantity,
      material_arrivals: [],
      completed_quantity: 0,
      remark: '',
      row_key: `material:${item.production_plan_item_id}:${material.material_type}:${material.material_no}:${index}`,
      is_material: true,
      has_materials: false,
      process_rowspan: 0,
    }))
    return [parent, ...materials]
  })
}

export function productionTaskSpan(
  departmentCode: string,
  row: ProductionTaskTreeRow,
  columnProperty?: string,
) {
  if (
    departmentCode !== 'assembly'
    || !columnProperty
    || !ASSEMBLY_MERGED_COLUMNS.has(columnProperty)
  ) return [1, 1]
  return row.is_material ? [0, 0] : [row.process_rowspan, 1]
}

export function displayWorkshopName(name: string) {
  return name.replace(/车间$/, '') || '—'
}
