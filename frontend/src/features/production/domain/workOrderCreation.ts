import type { ProcedureOption } from './types'

export type WorkOrderCreationTarget = {
  repository_id: number | null
  part_no: string
  part_name: string
  workshop_name: string
  available_quantity: number
  available_procedures: ProcedureOption[]
}

export type AssemblyWorkOrderCreationSource = {
  repository_id: number
  source_label: string
  available_quantity: number
}

export type AssemblyWorkOrderCreationMaterial = {
  material_key: string
  item_code: string
  item_name: string
  unit_quantity: number
  sources: AssemblyWorkOrderCreationSource[]
}

export type AssemblyWorkOrderCreationTarget = WorkOrderCreationTarget & {
  materials: AssemblyWorkOrderCreationMaterial[]
}

export type TaskWorkOrderChoice = {
  key: string
  position_key: string
  mode: 'standard' | 'assembly_initial' | 'assembly_continuation'
  repository_id: number | null
  label: string
  description: string
}
