import LogicFlow, {
  DiamondNode,
  DiamondNodeModel,
  PolylineEdge,
  PolylineEdgeModel,
  RectNode,
  RectNodeModel,
} from '@logicflow/core'
import { materialColors } from '@/shared/material/tokens'
import { obstacleAwarePoints } from './routePolyline'

function displayScale(properties: Record<string, unknown>) {
  const value = Number(properties.__displayScale)
  return Number.isFinite(value) && value > 0 ? value : 1
}

function fourMidpointAnchors(model: { id: string; x: number; y: number; width: number; height: number }) {
  const { id, x, y, width, height } = model
  return [
    { id: `${id}_0`, name: 'top', x, y: y - height / 2 },
    { id: `${id}_1`, name: 'right', x: x + width / 2, y },
    { id: `${id}_2`, name: 'bottom', x, y: y + height / 2 },
    { id: `${id}_3`, name: 'left', x: x - width / 2, y },
  ]
}

export class ProcessPolylineEdgeModel extends PolylineEdgeModel {
  updatePoints() {
    this.pointsList = obstacleAwarePoints(
      { ...this.startPoint },
      { ...this.endPoint },
      this.sourceAnchorId,
      this.targetAnchorId,
      this.sourceNodeId,
      this.targetNodeId,
      this.graphModel.nodes,
    )
    this.points = this.getPath(this.pointsList)
  }
}

class PartNodeModel extends RectNodeModel {
  initNodeData(data: LogicFlow.NodeConfig) {
    super.initNodeData(data)
    this.targetRules.push({
      message: '配件节点是流程起点，不能连接输入线',
      validate: () => false,
    })
    this.sourceRules.push({
      message: '配件后只能连接工艺、装配或委外加工节点',
      validate: (_sourceNode, targetNode) => (
        Boolean(
          targetNode
          && ['process', 'assembly', 'supplier_processing'].includes(targetNode.type),
        )
      ),
    })
  }

  setAttributes() {
    const scale = displayScale(this.properties)
    this.width = 150 * scale
    this.height = 56 * scale
    this.radius = 12 * scale
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.primaryContainer,
      stroke: materialColors.primary,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class ProcessNodeModel extends RectNodeModel {
  initNodeData(data: LogicFlow.NodeConfig) {
    super.initNodeData(data)
    this.sourceRules.push({
      message: '工艺节点后必须连接QC；装包节点可以直接连接入库',
      validate: (sourceNode, targetNode) => {
        const targetType = String(targetNode?.type ?? '')
        return Boolean(
          sourceNode
          && targetNode
          && (
            targetType === 'qc'
            || (
              sourceNode.properties.directInbound === true
              && targetType === 'finished_inbound'
            )
          ),
        )
      },
    })
  }

  setAttributes() {
    const scale = displayScale(this.properties)
    this.width = 150 * scale
    this.height = 56 * scale
    this.radius = 28 * scale
  }

  getNodeStyle() {
    const departmentCode = this.properties.departmentCode
    const colors = departmentCode === 'outsource'
      ? [materialColors.flowOutsourceContainer, materialColors.flowOutsource]
      : [materialColors.flowProductionContainer, materialColors.flowProduction]
    return {
      ...super.getNodeStyle(),
      fill: colors[0],
      stroke: colors[1],
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class QcNodeModel extends DiamondNodeModel {
  initNodeData(data: LogicFlow.NodeConfig) {
    super.initNodeData(data)
    this.targetRules.push({
      message: 'QC上游必须是工艺、装配或委外加工节点',
      validate: (sourceNode) => (
        Boolean(
          sourceNode
          && ['process', 'assembly', 'supplier_processing'].includes(sourceNode.type),
        )
      ),
    })
  }

  setAttributes() {
    const scale = displayScale(this.properties)
    this.rx = 68 * scale
    this.ry = 42 * scale
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.flowQcContainer,
      stroke: materialColors.flowQc,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class SupplierProcessingNodeModel extends RectNodeModel {
  initNodeData(data: LogicFlow.NodeConfig) {
    super.initNodeData(data)
    this.targetRules.push({
      message: '委外加工节点的上游必须是配件节点',
      validate: (sourceNode) => Boolean(sourceNode && ['part'].includes(sourceNode.type)),
    })
    this.sourceRules.push({
      message: '委外加工节点后只能连接QC节点',
      validate: (_sourceNode, targetNode) => Boolean(targetNode && ['qc'].includes(targetNode.type)),
    })
  }

  setAttributes() {
    const scale = displayScale(this.properties)
    this.width = 160 * scale
    this.height = 56 * scale
    this.radius = 12 * scale
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.flowSupplierProcessingContainer,
      stroke: materialColors.flowSupplierProcessing,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class FinishedInboundNodeModel extends RectNodeModel {
  setAttributes() {
    const scale = displayScale(this.properties)
    this.width = 150 * scale
    this.height = 56 * scale
    this.radius = 12 * scale
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.flowFinishedContainer,
      stroke: materialColors.flowFinished,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class AssemblyNodeModel extends RectNodeModel {
  setAttributes() {
    const scale = displayScale(this.properties)
    this.width = 160 * scale
    this.height = 56 * scale
    this.radius = 12 * scale
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.flowAssemblyContainer,
      stroke: materialColors.flowAssembly,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

export function registerProcessNodes(lf: LogicFlow) {
  lf.batchRegister([
    { type: 'polyline', view: PolylineEdge, model: ProcessPolylineEdgeModel },
    { type: 'part', view: RectNode, model: PartNodeModel },
    { type: 'process', view: RectNode, model: ProcessNodeModel },
    { type: 'qc', view: DiamondNode, model: QcNodeModel },
    { type: 'supplier_processing', view: RectNode, model: SupplierProcessingNodeModel },
    { type: 'finished_inbound', view: RectNode, model: FinishedInboundNodeModel },
    { type: 'assembly', view: RectNode, model: AssemblyNodeModel },
  ])
}
