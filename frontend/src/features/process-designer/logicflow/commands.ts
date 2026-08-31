import type LogicFlow from '@logicflow/core'
import type { BomItem } from '../domain/types'

export function startPartDrag(lf: LogicFlow, item: BomItem) {
  if (!item.id) throw new Error('请先保存 BOM 行')
  lf.dnd.startDrag({
    type: 'part',
    text: item.part_name,
    properties: { bomItemId: item.id, partNo: item.part_no },
  })
}

export function startProcessDrag(
  lf: LogicFlow,
  workshopId: number,
  workshopName: string,
  multiple: boolean,
  departmentCode: string,
) {
  if (multiple) {
    lf.dnd.startDrag({
      type: 'assembly',
      text: workshopName,
      properties: {
        workshopId,
        outputName: '装配体',
        outputPcs: 1,
      },
    })
    return
  }
  lf.dnd.startDrag({
    type: 'process',
    text: workshopName,
    properties: {
      workshopId,
      departmentCode,
      directInbound: departmentCode === 'assembly',
    },
  })
}

export function startQcDrag(lf: LogicFlow) {
  lf.dnd.startDrag({ type: 'qc', text: 'QC' })
}

export function startSupplierProcessingDrag(lf: LogicFlow) {
  lf.dnd.startDrag({ type: 'supplier_processing', text: '委外加工' })
}

export function startFinishedInboundDrag(lf: LogicFlow) {
  lf.dnd.startDrag({ type: 'finished_inbound', text: '入库' })
}

export function updateNodeDefinition(
  lf: LogicFlow,
  nodeId: string,
  label: string,
  property: {
    key: 'outputName' | 'outputPcs' | 'workshopId' | 'departmentCode'
    value: string | number | boolean
  } | null,
) {
  lf.updateText(nodeId, label)
  if (property) lf.setProperties(nodeId, { [property.key]: property.value })
}
