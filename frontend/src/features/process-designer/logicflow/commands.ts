import type LogicFlow from '@logicflow/core'
import type { BomItem } from '../domain/types'

export function startPartDrag(lf: LogicFlow, item: BomItem) {
  if (!item.id) throw new Error('请先保存 BOM 行')
  const duplicated = lf.getGraphRawData().nodes.some(
    (node) => node.type === 'part' && node.properties?.bomItemId === item.id,
  )
  if (duplicated) throw new Error(`“${item.part_name}”已存在于流程图中`)
  lf.dnd.startDrag({
    type: 'part',
    text: item.part_name,
    properties: { bomItemId: item.id, partNo: item.part_no },
  })
}

export function startProcessDrag(
  lf: LogicFlow,
  procedureId: number,
  procedureName: string,
) {
  lf.dnd.startDrag({
    type: 'process',
    text: procedureName,
    properties: {
      processCode: `procedure_${procedureId}`,
      procedureId,
      qcRequired: false,
    },
  })
}

export function startAssemblyDrag(lf: LogicFlow) {
  lf.dnd.startDrag({
    type: 'assembly',
    text: '装配',
    properties: { outputName: '装配体', outputPcs: 1 },
  })
}

export function updateNodeDefinition(
  lf: LogicFlow,
  nodeId: string,
  label: string,
  property: {
    key: 'processCode' | 'outputName' | 'outputPcs' | 'procedureId' | 'qcRequired'
    value: string | number | boolean
  } | null,
) {
  lf.updateText(nodeId, label)
  if (property) lf.setProperties(nodeId, { [property.key]: property.value })
}
