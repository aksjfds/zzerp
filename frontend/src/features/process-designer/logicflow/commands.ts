import type LogicFlow from '@logicflow/core'
import type { BomItem, RouteType } from '../domain/types'

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
    },
  })
}

export function startAssemblyDrag(lf: LogicFlow) {
  lf.dnd.startDrag({
    type: 'assembly',
    text: '装配',
    properties: { outputName: '装配体' },
  })
}

export function startQcDrag(lf: LogicFlow) {
  lf.dnd.startDrag({ type: 'qc', text: 'QC', properties: {} })
}

export function updateNodeDefinition(
  lf: LogicFlow,
  nodeId: string,
  label: string,
  property: {
    key: 'processCode' | 'outputName' | 'procedureId'
    value: string | number
  } | null,
) {
  lf.updateText(nodeId, label)
  if (property) lf.setProperties(nodeId, { [property.key]: property.value })
}

export function setQcEdgeRoute(lf: LogicFlow, edgeId: string, routeType: RouteType) {
  const edge = lf.getEdgeDataById(edgeId)
  if (!edge) throw new Error('连线不存在')
  const source = lf.getNodeDataById(edge.sourceNodeId)
  if (source?.type !== 'qc') throw new Error('只有从 QC 节点发出的连线可以设置合格或返工')
  const isRework = routeType === 'rework'
  lf.setProperties(edgeId, {
    routeType,
    outcome: isRework ? 'rejected' : 'approved',
  })
  lf.updateText(edgeId, isRework ? '不合格返工' : '合格')
}
