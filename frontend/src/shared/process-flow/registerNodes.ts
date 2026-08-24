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
      : departmentCode === 'purchasing'
        ? [materialColors.flowPurchasingContainer, materialColors.flowPurchasing]
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

class ShippingNodeModel extends RectNodeModel {
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
    { type: 'shipping', view: RectNode, model: ShippingNodeModel },
    { type: 'assembly', view: RectNode, model: AssemblyNodeModel },
  ])
}
