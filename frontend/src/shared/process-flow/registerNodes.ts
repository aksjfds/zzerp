import LogicFlow, {
  PolylineEdge,
  PolylineEdgeModel,
  RectNode,
  RectNodeModel,
} from '@logicflow/core'
import { readFlowColors } from '@/shared/theme/flowColors'
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

export function registerProcessNodes(lf: LogicFlow) {
  const flowColors = readFlowColors()
  lf.setTheme({
    nodeText: { ...lf.graphModel.theme.nodeText, color: flowColors.text },
    edgeText: { ...lf.graphModel.theme.edgeText, color: flowColors.text },
    polyline: { stroke: flowColors.outline },
    anchor: { fill: flowColors.surface, stroke: flowColors.primary },
    outline: { stroke: flowColors.primary },
    edgeOutline: { stroke: flowColors.primary },
  })

  class PartNodeModel extends RectNodeModel {
    initNodeData(data: LogicFlow.NodeConfig) {
      super.initNodeData(data)
      this.targetRules.push({ message: '配件节点是路线起点，不能连接输入线', validate: () => false })
    }

    setAttributes() {
      const scale = displayScale(this.properties)
      this.width = 150 * scale
      this.height = 56 * scale
      this.radius = 8 * scale
    }

    getNodeStyle() {
      return {
        ...super.getNodeStyle(),
        fill: flowColors.primaryContainer,
        stroke: flowColors.primary,
        strokeWidth: 2,
      }
    }

    getDefaultAnchor() {
      return fourMidpointAnchors(this)
    }
  }

  class DepartmentNodeModel extends RectNodeModel {
    setAttributes() {
      const scale = displayScale(this.properties)
      this.width = 150 * scale
      this.height = 56 * scale
      this.radius = 28 * scale
    }
    getNodeStyle() {
      return { ...super.getNodeStyle(), fill: flowColors.surface, stroke: flowColors.primary, strokeWidth: 2 }
    }
    getDefaultAnchor() { return fourMidpointAnchors(this) }
  }

  lf.batchRegister([
    { type: 'polyline', view: PolylineEdge, model: ProcessPolylineEdgeModel },
    { type: 'part', view: RectNode, model: PartNodeModel },
    { type: 'department', view: RectNode, model: DepartmentNodeModel },
  ])
}
