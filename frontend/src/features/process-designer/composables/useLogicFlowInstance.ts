import { nextTick, onBeforeUnmount, onMounted, shallowRef, type Ref } from 'vue'
import LogicFlow from '@logicflow/core'
import { Control, Menu } from '@logicflow/extension'
import { registerProcessNodes } from '@/shared/process-flow/registerNodes'
import {
  fromLogicFlowData,
  PROCESS_FLOW_GRID_X,
  PROCESS_FLOW_GRID_Y,
  toLogicFlowData,
} from '@/shared/process-flow/adapter'
import { updateProcessCanvasScale } from '@/shared/process-flow/nodeTextScale'
import {
  applyProcessNodeScale,
  PROCESS_FLOW_FONT_SIZE_STORAGE_KEY,
  PROCESS_FLOW_MIN_CANVAS_SCALE,
  PROCESS_FLOW_NODE_SCALE_STORAGE_KEY,
  storedProcessFlowNumber,
} from '@/shared/process-flow/canvasDisplay'
import type { FlowEdge, FlowNode, ProcessFlow } from '../domain/types'
import { createCanvasPointerInteractions } from './canvasPointerInteractions'
import { planAutoConnections } from './processAutoConnect'
import { replanConnectedEdges, snapNodeToGrid, snapSelectionToGrid } from './processCanvasGrid'

type Callbacks = {
  initialFlow: () => ProcessFlow
  readonly?: () => boolean
  onChange: (flow: ProcessFlow) => void
  onConnectionError: (message: string) => void
  onSelectEdge: (edge: FlowEdge | null) => void
  onSelectNode: (node: FlowNode | null) => void
  workshopDepartmentCode?: (workshopId: number) => string | undefined
  workshopDirectInbound?: (workshopId: number) => boolean
}

type SelectedElements = ReturnType<LogicFlow['getSelectElements']>

export function useLogicFlowInstance(container: Ref<HTMLDivElement | undefined>, callbacks: Callbacks) {
  const instance = shallowRef<LogicFlow | null>(null)
  let resizeObserver: ResizeObserver | null = null
  let resizeFrame: number | null = null
  let fontSize = storedProcessFlowNumber(PROCESS_FLOW_FONT_SIZE_STORAGE_KEY, 13, 10)
  let nodeDisplayScale = storedProcessFlowNumber(PROCESS_FLOW_NODE_SCALE_STORAGE_KEY, 1, 0.6)
  let applyingDisplayScale = false
  let batchConnecting = false
  let batchDeleting = false
  let panElement: HTMLDivElement | null = null
  const pointerInteractions = createCanvasPointerInteractions({
    container: () => panElement,
    logicFlow: () => instance.value,
    fitCanvas: fitCanvasToContent,
  })

  function changeFontSize(delta: number) {
    fontSize = Math.max(10, fontSize + delta)
    container.value?.style.setProperty('--process-node-font-size', `${fontSize}px`)
    localStorage.setItem(PROCESS_FLOW_FONT_SIZE_STORAGE_KEY, String(fontSize))
  }

  function changeNodeSize(delta: number) {
    nodeDisplayScale = Math.max(0.6, Number((nodeDisplayScale + delta).toFixed(2)))
    localStorage.setItem(PROCESS_FLOW_NODE_SCALE_STORAGE_KEY, String(nodeDisplayScale))
    if (instance.value) applyNodeDisplayScale(instance.value)
  }

  function fitCanvasToContent(lf: LogicFlow) {
    requestAnimationFrame(() => {
      if (instance.value !== lf) return
      lf.fitView(48, 48)
      refreshNodeReadability(lf)
    })
  }

  function autoConnectSelectedNodes(lf: LogicFlow) {
    planAutoConnections(lf, callbacks.onConnectionError, (edges) => {
      batchConnecting = true
      try {
        edges.forEach(edge => lf.addEdge({ type: 'polyline', ...edge }))
      } finally {
        batchConnecting = false
      }
      lf.clearSelectElements()
      emitChange()
    })
  }

  function deleteSelectedNodes(lf: LogicFlow, elements?: SelectedElements) {
    const selectedNodes = elements?.nodes ?? lf.getSelectElements().nodes
    if (!selectedNodes.length) return
    batchDeleting = true
    try {
      lf.clearSelectElements()
      selectedNodes.forEach(node => lf.deleteNode(node.id))
    } finally {
      batchDeleting = false
    }
    callbacks.onSelectNode(null)
    callbacks.onSelectEdge(null)
    emitChange()
  }

  function applyNodeDisplayScale(lf: LogicFlow, nodeId?: string) {
    applyingDisplayScale = true
    applyProcessNodeScale(lf, nodeDisplayScale, nodeId)
    applyingDisplayScale = false
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
      stopMoveGraph: true,
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
        : [
            { text: '自动连接', callback: () => autoConnectSelectedNodes(lf) },
            { text: '删除节点', callback: (node: { id: string }) => lf.deleteNode(node.id) },
          ],
      edgeMenu: readonly
        ? []
        : [{ text: '删除连线', callback: (edge: { id: string }) => lf.deleteEdge(edge.id) }],
      graphMenu: [],
      selectionMenu: readonly
        ? []
        : [
            { text: '自动连接', callback: () => autoConnectSelectedNodes(lf) },
            { text: '删除所选节点', callback: (elements: SelectedElements) => deleteSelectedNodes(lf, elements) },
          ],
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
      workshopDepartmentCode: callbacks.workshopDepartmentCode,
      workshopDirectInbound: callbacks.workshopDirectInbound,
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
      grid: { size: PROCESS_FLOW_GRID_Y, visible: true },
      snapGrid: false,
      edgeType: 'polyline',
      keyboard: { enabled: true },
      stopMoveGraph: true,
      stopScrollGraph: true,
      stopZoomGraph: true,
      guards: {
        beforeClone: () => !(callbacks.readonly?.() ?? false),
        beforeDelete: () => !(callbacks.readonly?.() ?? false),
      },
      plugins: [Control, Menu],
    })
    instance.value = lf
    lf.setZoomMiniSize(PROCESS_FLOW_MIN_CANVAS_SCALE)
    registerProcessNodes(lf)
    setReadonly(callbacks.readonly?.() ?? false)
    panElement = container.value
    pointerInteractions.bind(panElement)
    lf.on('edge:add', () => {
      if (!batchConnecting) emitChange()
    })
    lf.on('node:add,node:dnd-add', ({ data }) => {
      applyNodeDisplayScale(lf, data.id)
      snapNodeToGrid(lf, data.id)
    })
    lf.on('node:drop', ({ data }) => {
      snapSelectionToGrid(lf, data.id)
      const selectedNodeIds = lf.getSelectElements().nodes.map(node => node.id)
      replanConnectedEdges(lf, selectedNodeIds.length ? selectedNodeIds : [data.id])
    })
    lf.on('selection:drop', () => {
      snapSelectionToGrid(lf)
      replanConnectedEdges(
        lf,
        lf.getSelectElements().nodes.map(node => node.id),
      )
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
        if (applyingDisplayScale || batchDeleting) return
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
    pointerInteractions.dispose(panElement)
    panElement = null
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
