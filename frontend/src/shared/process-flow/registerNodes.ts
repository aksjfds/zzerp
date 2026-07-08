import LogicFlow, {
  DiamondNode,
  DiamondNodeModel,
  RectNode,
  RectNodeModel,
} from '@logicflow/core'

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
    this.radius = 8
  }

  getNodeStyle() {
    return { ...super.getNodeStyle(), fill: '#ecf5ff', stroke: '#409eff', strokeWidth: 2 }
  }
}

class ProcessNodeModel extends RectNodeModel {
  setAttributes() {
    this.width = 150
    this.height = 56
    this.radius = 28
  }

  getNodeStyle() {
    return { ...super.getNodeStyle(), fill: '#f0f9eb', stroke: '#67c23a', strokeWidth: 2 }
  }
}

class AssemblyNodeModel extends DiamondNodeModel {
  setAttributes() {
    this.rx = 88
    this.ry = 54
  }

  getNodeStyle() {
    return { ...super.getNodeStyle(), fill: '#fdf6ec', stroke: '#e6a23c', strokeWidth: 2 }
  }
}

class QcNodeModel extends DiamondNodeModel {
  setAttributes() {
    this.rx = 68
    this.ry = 48
  }

  getNodeStyle() {
    return { ...super.getNodeStyle(), fill: '#fef0f0', stroke: '#f56c6c', strokeWidth: 2 }
  }
}

export function registerProcessNodes(lf: LogicFlow) {
  lf.batchRegister([
    { type: 'part', view: RectNode, model: PartNodeModel },
    { type: 'process', view: RectNode, model: ProcessNodeModel },
    { type: 'assembly', view: DiamondNode, model: AssemblyNodeModel },
    { type: 'qc', view: DiamondNode, model: QcNodeModel },
  ])
}
