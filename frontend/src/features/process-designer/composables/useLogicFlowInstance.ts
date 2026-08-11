import { nextTick, onBeforeUnmount, onMounted, shallowRef, type Ref } from 'vue'
import LogicFlow from '@logicflow/core'
import { Control, Menu } from '@logicflow/extension'
import { registerProcessNodes } from '@/shared/process-flow/registerNodes'
import {
  fromLogicFlowData,
  PROCESS_FLOW_GRID_SIZE,
  toLogicFlowData,
} from '@/shared/process-flow/adapter'
import { updateProcessCanvasScale } from '@/shared/process-flow/nodeTextScale'
import type { FlowEdge, FlowNode, ProcessFlow } from '../domain/types'

const FONT_SIZE_STORAGE_KEY = 'zzerp.processFlow.fontSize'
const NODE_SCALE_STORAGE_KEY = 'zzerp.processFlow.nodeScale'

type Callbacks = {
  initialFlow: () => ProcessFlow
  readonly?: () => boolean
  onChange: (flow: ProcessFlow) => void
  onConnectionError: (message: string) => void
  onSelectEdge: (edge: FlowEdge | null) => void
  onSelectNode: (node: FlowNode | null) => void
  processDepartmentCode?: (procedureId: number) => string | undefined
}

export function useLogicFlowInstance(container: Ref<HTMLDivElement | undefined>, callbacks: Callbacks) {
  const instance = shallowRef<LogicFlow | null>(null)
  let resizeObserver: ResizeObserver | null = null
  let resizeFrame: number | null = null
  let fontSize = storedNumber(FONT_SIZE_STORAGE_KEY, 13, 10)
  let nodeDisplayScale = storedNumber(NODE_SCALE_STORAGE_KEY, 1, 0.6, 1.8)
  let applyingDisplayScale = false

  function changeFontSize(delta: number) {
    fontSize = Math.max(10, fontSize + delta)
    container.value?.style.setProperty('--process-node-font-size', `${fontSize}px`)
    localStorage.setItem(FONT_SIZE_STORAGE_KEY, String(fontSize))
  }

  function changeNodeSize(delta: number) {
    nodeDisplayScale = Math.min(1.8, Math.max(0.6, nodeDisplayScale + delta))
    localStorage.setItem(NODE_SCALE_STORAGE_KEY, String(nodeDisplayScale))
    if (instance.value) applyNodeDisplayScale(instance.value)
  }

  function snapNodeToGrid(lf: LogicFlow, nodeId: string) {
    const node = lf.getNodeModelById(nodeId)
    if (!node) return
    const x = Math.round(node.x / PROCESS_FLOW_GRID_SIZE) * PROCESS_FLOW_GRID_SIZE
    const y = Math.round(node.y / PROCESS_FLOW_GRID_SIZE) * PROCESS_FLOW_GRID_SIZE
    if (x !== node.x || y !== node.y) {
      lf.graphModel.moveNode2Coordinate(nodeId, x, y, true)
    }
  }

  function fitCanvasToContent(lf: LogicFlow) {
    requestAnimationFrame(() => {
      if (instance.value !== lf) return
      lf.fitView(32, 32)
      refreshNodeReadability(lf)
    })
  }

  function applyNodeDisplayScale(lf: LogicFlow, nodeId?: string) {
    const nodeIds = nodeId ? [nodeId] : lf.graphModel.nodes.map(node => node.id)
    applyingDisplayScale = true
    nodeIds.forEach((id) => {
      const model = lf.getNodeModelById(id)
      if (model?.properties.__displayScale !== nodeDisplayScale) {
        lf.setProperties(id, { __displayScale: nodeDisplayScale })
      }
    })
    applyingDisplayScale = false
    refreshEdgeEndpoints(lf)
  }

  function refreshEdgeEndpoints(lf: LogicFlow) {
    lf.graphModel.edges.forEach((edge) => {
      const sourceNode = edge.sourceNode
      const targetNode = edge.targetNode
      const startPoint = edge.getBeginAnchor(
        sourceNode,
        targetNode,
        edge.sourceAnchorId,
      )
      const endPoint = edge.getEndAnchor(targetNode, edge.targetAnchorId)
      if (!startPoint || !endPoint) return
      const pointsList = edge.pointsList.length
        ? edge.pointsList.map((point, index, points) => (
          index === 0
            ? { x: startPoint.x, y: startPoint.y }
            : index === points.length - 1
              ? { x: endPoint.x, y: endPoint.y }
              : point
        ))
        : []
      edge.updateAttributes({
        startPoint: { x: startPoint.x, y: startPoint.y },
        endPoint: { x: endPoint.x, y: endPoint.y },
        pointsList,
      })
      edge.initPoints()
    })
  }

  function refreshNodeReadability(lf: LogicFlow) {
    requestAnimationFrame(() => {
      if (!container.value || instance.value !== lf) return
      updateProcessCanvasScale(
        container.value,
        lf.graphModel.transformModel.SCALE_X,
      )
    })
  }

  function resizeCanvas() {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = null
      const element = container.value
      const lf = instance.value
      if (!element || !lf) return
      lf.resize(element.clientWidth, element.clientHeight)
    })
  }

  function setReadonly(readonly: boolean) {
    const lf = instance.value
    if (!lf) return
    lf.updateEditConfig({
      adjustEdge: !readonly,
      adjustEdgeEnd: !readonly,
      adjustEdgeMiddle: !readonly,
      adjustEdgeStart: !readonly,
      adjustEdgeStartAndEnd: !readonly,
      adjustNodePosition: !readonly,
      allowResize: !readonly,
      allowRotate: !readonly,
      edgeTextDraggable: !readonly,
      edgeTextEdit: !readonly,
      hideAnchors: readonly,
      nodeTextDraggable: false,
      nodeTextEdit: !readonly,
      stopMoveGraph: false,
      stopScrollGraph: true,
      stopZoomGraph: true,
      textDraggable: !readonly,
      textEdit: !readonly,
      snapGrid: false,
    })
    const menu = lf.extension.menu as Menu
    menu.setMenuConfig({
      nodeMenu: readonly
        ? []
        : [{ text: '删除节点', callback: (node: { id: string }) => lf.deleteNode(node.id) }],
      edgeMenu: readonly
        ? []
        : [{ text: '删除连线', callback: (edge: { id: string }) => lf.deleteEdge(edge.id) }],
      graphMenu: [],
    })
  }

  function currentFlow() {
    if (!instance.value) return callbacks.initialFlow()
    return fromLogicFlowData(instance.value.getGraphRawData())
  }

  function emitChange() {
    callbacks.onChange(currentFlow())
  }

  function renderFlow(flow: ProcessFlow) {
    const lf = instance.value
    lf?.renderRawData(toLogicFlowData(flow, {
      processDepartmentCode: callbacks.processDepartmentCode,
    }))
    if (lf) {
      applyNodeDisplayScale(lf)
      refreshNodeReadability(lf)
    }
  }

  onMounted(async () => {
    await nextTick()
    if (!container.value) return
    container.value.style.setProperty('--process-node-font-size', `${fontSize}px`)
    const lf = new LogicFlow({
      container: container.value,
      grid: { size: PROCESS_FLOW_GRID_SIZE, visible: true },
      snapGrid: false,
      edgeType: 'polyline',
      keyboard: { enabled: true },
      stopMoveGraph: false,
      stopScrollGraph: true,
      stopZoomGraph: true,
      guards: {
        beforeClone: () => !(callbacks.readonly?.() ?? false),
        beforeDelete: () => !(callbacks.readonly?.() ?? false),
      },
      plugins: [Control, Menu],
    })
    instance.value = lf
    registerProcessNodes(lf)
    setReadonly(callbacks.readonly?.() ?? false)
    lf.on('edge:add', () => {
      emitChange()
    })
    lf.on('node:add,node:dnd-add', ({ data }) => {
      applyNodeDisplayScale(lf, data.id)
      snapNodeToGrid(lf, data.id)
    })
    lf.on('node:drop', ({ data }) => {
      snapNodeToGrid(lf, data.id)
    })
    lf.on('node:click', ({ data }) => {
      const node = currentFlow().nodes.find((item) => item.id === data.id) ?? null
      callbacks.onSelectEdge(null)
      callbacks.onSelectNode(node)
    })
    lf.on('edge:click', ({ data }) => {
      const edge = currentFlow().edges.find((item) => item.id === data.id) ?? null
      callbacks.onSelectNode(null)
      callbacks.onSelectEdge(edge)
    })
    lf.on('blank:click', () => {
      callbacks.onSelectNode(null)
      callbacks.onSelectEdge(null)
    })
    lf.on(
      'node:add,node:dnd-add,node:delete,edge:delete,node:drop,node:rotate,node:resize,node:properties-change,edge:adjust,edge:exchange-node,text:update',
      () => {
        if (applyingDisplayScale) return
        emitChange()
        refreshNodeReadability(lf)
      },
    )
    lf.on('connection:not-allowed', ({ msg }) => {
      callbacks.onConnectionError(msg || '该连线不符合流程规则')
    })
    lf.on('graph:transform', ({ type, transform }) => {
      if (container.value) updateProcessCanvasScale(container.value, transform.SCALE_X)
      if (type === 'resetZoom') {
        fitCanvasToContent(lf)
      }
    })
    renderFlow(callbacks.initialFlow())
    resizeObserver = new ResizeObserver(resizeCanvas)
    resizeObserver.observe(container.value)
    resizeCanvas()
    fitCanvasToContent(lf)
  })

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    resizeObserver = null
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    resizeFrame = null
    instance.value?.destroy()
    instance.value = null
  })

  return {
    changeFontSize,
    changeNodeSize,
    currentFlow,
    emitChange,
    instance,
    renderFlow,
    setReadonly,
  }
}

function storedNumber(
  key: string,
  fallback: number,
  minimum: number,
  maximum = Number.POSITIVE_INFINITY,
) {
  const stored = localStorage.getItem(key)
  if (stored === null || stored.trim() === '') return fallback
  const value = Number(stored)
  return Number.isFinite(value)
    ? Math.min(maximum, Math.max(minimum, value))
    : fallback
}
