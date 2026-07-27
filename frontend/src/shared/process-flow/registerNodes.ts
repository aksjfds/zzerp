import LogicFlow, {
  DiamondNode,
  DiamondNodeModel,
  RectNode,
  RectNodeModel,
} from '@logicflow/core'
import { materialColors } from '@/shared/material/tokens'

function fourMidpointAnchors(model: { id: string; x: number; y: number; width: number; height: number }) {
  const { id, x, y, width, height } = model
  return [
    { id: `${id}_0`, name: 'top', x, y: y - height / 2 },
    { id: `${id}_1`, name: 'right', x: x + width / 2, y },
    { id: `${id}_2`, name: 'bottom', x, y: y + height / 2 },
    { id: `${id}_3`, name: 'left', x: x - width / 2, y },
  ]
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
    this.width = 150
    this.height = 56
    this.radius = 12
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
    this.width = 150
    this.height = 56
    this.radius = 28
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.successContainer,
      stroke: materialColors.success,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class QcNodeModel extends RectNodeModel {
  setAttributes() {
    this.width = 120
    this.height = 56
    this.radius = 12
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.tertiaryContainer,
      stroke: materialColors.tertiary,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class ShippingNodeModel extends RectNodeModel {
  setAttributes() {
    this.width = 150
    this.height = 56
    this.radius = 12
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.secondaryContainer,
      stroke: materialColors.secondary,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

class AssemblyNodeModel extends DiamondNodeModel {
  setAttributes() {
    this.rx = 88
    this.ry = 54
  }

  getNodeStyle() {
    return {
      ...super.getNodeStyle(),
      fill: materialColors.warningContainer,
      stroke: materialColors.warning,
      strokeWidth: 2,
    }
  }

  getDefaultAnchor() {
    return fourMidpointAnchors(this)
  }
}

export function registerProcessNodes(lf: LogicFlow) {
  lf.batchRegister([
    { type: 'part', view: RectNode, model: PartNodeModel },
    { type: 'process', view: RectNode, model: ProcessNodeModel },
    { type: 'qc', view: RectNode, model: QcNodeModel },
    { type: 'shipping', view: RectNode, model: ShippingNodeModel },
    { type: 'assembly', view: DiamondNode, model: AssemblyNodeModel },
  ])
}
