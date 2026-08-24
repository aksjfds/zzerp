import LogicFlow, { PolylineEdge } from '@logicflow/core'
import { Control } from '@logicflow/extension'
import { PROCESS_FLOW_GRID_Y } from './adapter'
import { PROCESS_FLOW_MIN_CANVAS_SCALE } from './canvasDisplay'
import {
  ProcessPolylineEdgeModel,
  registerProcessNodes,
} from './registerNodes'

class ProductionPolylineEdgeModel extends ProcessPolylineEdgeModel {
  getEdgeAnimationStyle() {
    const style = super.getEdgeAnimationStyle()
    const properties = this.properties as Record<string, unknown>
    const animationStyle = properties.productionAnimationStyle
    return {
      ...style,
      ...(isRecord(animationStyle) ? animationStyle : {}),
    }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function createProductionFlowInstance(container: HTMLDivElement) {
  const instance = new LogicFlow({
    container,
    isSilentMode: true,
    grid: { size: PROCESS_FLOW_GRID_Y, visible: true },
    snapGrid: false,
    edgeType: 'polyline',
    stopZoomGraph: true,
    stopScrollGraph: true,
    stopMoveGraph: true,
    plugins: [Control],
  })
  instance.setZoomMiniSize(PROCESS_FLOW_MIN_CANVAS_SCALE)
  registerProcessNodes(instance)
  instance.batchRegister([
    { type: 'production-polyline', view: PolylineEdge, model: ProductionPolylineEdgeModel },
  ])
  return instance
}
