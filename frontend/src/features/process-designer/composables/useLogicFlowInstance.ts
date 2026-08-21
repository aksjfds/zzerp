import { nextTick, onBeforeUnmount, onMounted, shallowRef, type Ref } from 'vue'
import LogicFlow, { type BaseNodeModel } from '@logicflow/core'
import { Control, Menu } from '@logicflow/extension'
import {
  ProcessPolylineEdgeModel,
  registerProcessNodes,
} from '@/shared/process-flow/registerNodes'
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

type Callbacks = {
  initialFlow: () => ProcessFlow
  readonly?: () => boolean
  onChange: (flow: ProcessFlow) => void
  onConnectionError: (message: string) => void
  onSelectEdge: (edge: FlowEdge | null) => void
  onSelectNode: (node: FlowNode | null) => void
  workshopDepartmentCode?: (workshopId: number) => string | undefined
}

export function useLogicFlowInstance(container: Ref<HTMLDivElement | undefined>, callbacks: Callbacks) {
  const instance = shallowRef<LogicFlow | null>(null)
  let resizeObserver: ResizeObserver | null = null
  let resizeFrame: number | null = null
  let fontSize = storedProcessFlowNumber(PROCESS_FLOW_FONT_SIZE_STORAGE_KEY, 13, 10)
  let nodeDisplayScale = storedProcessFlowNumber(PROCESS_FLOW_NODE_SCALE_STORAGE_KEY, 1, 0.6)
  let applyingDisplayScale = false
  let batchConnecting = false
  let panElement: HTMLDivElement | null = null
  let middlePanPoint: { x: number; y: number } | null = null
  let selectionStart: { clientX: number; clientY: number; x: number; y: number } | null = null
  let selectionBox: HTMLDivElement | null = null

  function handleMiddlePanStart(event: PointerEvent) {
    if (event.button !== 1 || !instance.value) return
    event.preventDefault()
    event.stopPropagation()
    middlePanPoint = { x: event.clientX, y: event.clientY }
    panElement?.classList.add('is-middle-panning')
  }

  function handleMiddlePanMove(event: PointerEvent) {
    const lf = instance.value
    if (!middlePanPoint || !lf) return
    event.preventDefault()
    lf.translate(
      event.clientX - middlePanPoint.x,
      event.clientY - middlePanPoint.y,
    )
    middlePanPoint = { x: event.clientX, y: event.clientY }
  }

  function handleMiddlePanEnd(event: PointerEvent) {
    if (event.button !== 1 || !middlePanPoint) return
    middlePanPoint = null
    panElement?.classList.remove('is-middle-panning')
  }

  function preventMiddleAuxClick(event: MouseEvent) {
    if (event.button === 1) event.preventDefault()
  }

  function handleOverviewClick(event: MouseEvent) {
    const target = event.target
    const controlItem = target instanceof Element ? target.closest('.lf-control-item') : null
    if (!controlItem?.querySelector('.lf-control-fit')) return
    const lf = instance.value
    if (!lf) return
    event.preventDefault()
    event.stopPropagation()
    fitCanvasToContent(lf)
  }

  function handleSelectionStart(event: PointerEvent) {
    if (event.button !== 0 || !instance.value || !panElement) return
    const target = event.target
    if (!(target instanceof Element)
      || !target.closest('.lf-canvas-overlay')
      || target.closest('.lf-node, .lf-edge, .lf-anchor, .lf-control, .lf-menu')) return
    event.preventDefault()
    event.stopPropagation()
    const rect = panElement.getBoundingClientRect()
    selectionStart = {
      clientX: event.clientX,
      clientY: event.clientY,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
    instance.value.clearSelectElements()
    selectionBox = document.createElement('div')
    selectionBox.className = 'process-selection-box'
    selectionBox.style.left = `${selectionStart.x}px`
    selectionBox.style.top = `${selectionStart.y}px`
    selectionBox.style.width = '0'
    selectionBox.style.height = '0'
    panElement.appendChild(selectionBox)
  }

  function handleSelectionMove(event: PointerEvent) {
    if (!selectionStart || !selectionBox || !panElement) return
    event.preventDefault()
    const rect = panElement.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    selectionBox.style.left = `${Math.min(selectionStart.x, x)}px`
    selectionBox.style.top = `${Math.min(selectionStart.y, y)}px`
    selectionBox.style.width = `${Math.abs(x - selectionStart.x)}px`
    selectionBox.style.height = `${Math.abs(y - selectionStart.y)}px`
  }

  function handleSelectionEnd(event: PointerEvent) {
    const lf = instance.value
    if (event.button !== 0 || !selectionStart || !lf) return
    const start = selectionStart
    const width = Math.abs(event.clientX - start.clientX)
    const height = Math.abs(event.clientY - start.clientY)
    selectionStart = null
    selectionBox?.remove()
    selectionBox = null
    if (width < 6 || height < 6) return
    const startPoint = lf.getPointByClient(start.clientX, start.clientY).domOverlayPosition
    const endPoint = lf.getPointByClient(event.clientX, event.clientY).domOverlayPosition
    const leftTop: [number, number] = [
      Math.min(startPoint.x, endPoint.x),
      Math.min(startPoint.y, endPoint.y),
    ]
    const rightBottom: [number, number] = [
      Math.max(startPoint.x, endPoint.x),
      Math.max(startPoint.y, endPoint.y),
    ]
    lf.graphModel
      .getAreaElement(leftTop, rightBottom, true, false, true)
      .filter(element => Boolean(lf.getNodeModelById(element.id)))
      .forEach(node => lf.selectElementById(node.id, true))
  }

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

  function snapNodeToGrid(lf: LogicFlow, nodeId: string) {
    const node = lf.getNodeModelById(nodeId)
    if (!node) return
    const x = Math.round(node.x / PROCESS_FLOW_GRID_X) * PROCESS_FLOW_GRID_X
    const y = Math.round(node.y / PROCESS_FLOW_GRID_Y) * PROCESS_FLOW_GRID_Y
    if (x !== node.x || y !== node.y) {
      lf.graphModel.moveNode2Coordinate(nodeId, x, y, true)
    }
  }

  function snapSelectionToGrid(lf: LogicFlow, anchorNodeId?: string) {
    const selectedNodes = lf.getSelectElements().nodes
    const anchor = anchorNodeId
      ? selectedNodes.find(node => node.id === anchorNodeId)
      : selectedNodes[0]
    if (!anchor) {
      if (anchorNodeId) snapNodeToGrid(lf, anchorNodeId)
      return
    }
    const deltaX = Math.round(anchor.x / PROCESS_FLOW_GRID_X) * PROCESS_FLOW_GRID_X - anchor.x
    const deltaY = Math.round(anchor.y / PROCESS_FLOW_GRID_Y) * PROCESS_FLOW_GRID_Y - anchor.y
    if (deltaX === 0 && deltaY === 0) return
    selectedNodes.forEach((node) => {
      lf.graphModel.moveNode2Coordinate(
        node.id,
        node.x + deltaX,
        node.y + deltaY,
        true,
      )
    })
  }

  function replanConnectedEdges(lf: LogicFlow, nodeIds: string[]) {
    const movedNodeIds = new Set(nodeIds)
    lf.graphModel.edges.forEach((edge) => {
      if (!(edge instanceof ProcessPolylineEdgeModel)
        || (!movedNodeIds.has(edge.sourceNodeId) && !movedNodeIds.has(edge.targetNodeId))) return
      edge.updatePoints()
    })
  }

  function fitCanvasToContent(lf: LogicFlow) {
    requestAnimationFrame(() => {
      if (instance.value !== lf) return
      lf.fitView(48, 48)
      refreshNodeReadability(lf)
    })
  }

  function autoConnectSelectedNodes(lf: LogicFlow) {
    const selectedIds = new Set(lf.getSelectElements().nodes.map(node => node.id))
    const selectedNodes = lf.graphModel.nodes.filter(node => selectedIds.has(node.id))
    const xValues = selectedNodes.map(node => node.x)
    const yValues = selectedNodes.map(node => node.y)
    const horizontal = selectedNodes.length > 1
      && (Math.max(...xValues) - Math.min(...xValues)) / PROCESS_FLOW_GRID_X
        > (Math.max(...yValues) - Math.min(...yValues)) / PROCESS_FLOW_GRID_Y
    const primaryPosition = (node: BaseNodeModel) => horizontal ? node.x : node.y
    const secondaryPosition = (node: BaseNodeModel) => horizontal ? node.y : node.x
    const nodes = selectedNodes.sort((left, right) => (
      primaryPosition(left) - primaryPosition(right)
      || secondaryPosition(left) - secondaryPosition(right)
    ))
    if (nodes.length < 2) {
      callbacks.onConnectionError('请先框选至少两个节点')
      return
    }

    const existingEdges = lf.graphModel.edges
    const existingPairs = new Set(
      existingEdges.map(edge => `${edge.sourceNodeId}->${edge.targetNodeId}`),
    )
    const incoming = new Map<string, number>()
    const outgoing = new Map<string, number>()
    const adjacency = new Map<string, Set<string>>()
    existingEdges.forEach((edge) => {
      incoming.set(edge.targetNodeId, (incoming.get(edge.targetNodeId) ?? 0) + 1)
      outgoing.set(edge.sourceNodeId, (outgoing.get(edge.sourceNodeId) ?? 0) + 1)
      adjacency.set(edge.sourceNodeId, new Set([
        ...(adjacency.get(edge.sourceNodeId) ?? []),
        edge.targetNodeId,
      ]))
    })

    const pending: Array<{ sourceNodeId: string; targetNodeId: string }> = []
    for (const source of nodes) {
      const forwardNodes = nodes.filter(
        target => primaryPosition(target) > primaryPosition(source),
      )
      if (!forwardNodes.length) continue
      const nextLayerPosition = Math.min(...forwardNodes.map(primaryPosition))
      const candidates = forwardNodes
        .filter(target => primaryPosition(target) === nextLayerPosition)
        .sort((left, right) => (
          Math.abs(secondaryPosition(left) - secondaryPosition(source))
          - Math.abs(secondaryPosition(right) - secondaryPosition(source))
          || secondaryPosition(left) - secondaryPosition(right)
        ))
      const existingTarget = candidates.find(candidate => (
        existingPairs.has(`${source.id}->${candidate.id}`)
      ))
      if ((outgoing.get(source.id) ?? 0) >= 1) {
        if (existingTarget) continue
        const sourceLabel = source.text.value || source.type
        callbacks.onConnectionError(`节点“${sourceLabel}”已经连接了其他后续节点`)
        return
      }
      const target = candidates.find((candidate) => {
        const pairKey = `${source.id}->${candidate.id}`
        return !existingPairs.has(pairKey)
          && !batchConnectionError(source, candidate, incoming, outgoing, adjacency)
      })
      if (!target) {
        const error = batchConnectionError(
          source,
          candidates[0],
          incoming,
          outgoing,
          adjacency,
        )
        callbacks.onConnectionError(error || '相邻节点无法连接')
        return
      }
      const pairKey = `${source.id}->${target.id}`
      pending.push({ sourceNodeId: source.id, targetNodeId: target.id })
      existingPairs.add(pairKey)
      incoming.set(target.id, (incoming.get(target.id) ?? 0) + 1)
      outgoing.set(source.id, (outgoing.get(source.id) ?? 0) + 1)
      adjacency.set(source.id, new Set([...(adjacency.get(source.id) ?? []), target.id]))
    }
    if (!pending.length) {
      callbacks.onConnectionError('所选节点之间没有可新增的有效连接')
      return
    }
    batchConnecting = true
    try {
      pending.forEach(edge => lf.addEdge({ type: 'polyline', ...edge }))
    } finally {
      batchConnecting = false
    }
    lf.clearSelectElements()
    emitChange()
  }

  function batchConnectionError(
    source: BaseNodeModel,
    target: BaseNodeModel,
    incoming: Map<string, number>,
    outgoing: Map<string, number>,
    adjacency: Map<string, Set<string>>,
  ) {
    const sourceLabel = source.text.value || source.type
    const targetLabel = target.text.value || target.type
    if (source.type === 'shipping') return `发货节点“${sourceLabel}”不能连接后续节点`
    if (target.type === 'part') return `配件节点“${targetLabel}”不能连接输入线`
    if ((outgoing.get(source.id) ?? 0) >= 1) return `节点“${sourceLabel}”已经有后续节点`
    if (['process', 'qc', 'shipping'].includes(target.type)
      && (incoming.get(target.id) ?? 0) >= 1) {
      return `节点“${targetLabel}”已经有上游节点`
    }
    if (source.type === 'part' && !['process', 'assembly'].includes(target.type)) {
      return `配件“${sourceLabel}”后只能连接工艺或装配节点`
    }
    if (target.type === 'qc' && !['process', 'assembly'].includes(source.type)) {
      return `QC节点“${targetLabel}”的上游必须是工艺或装配节点`
    }
    if (source.type === 'qc' && !['process', 'assembly', 'shipping'].includes(target.type)) {
      return `QC节点“${sourceLabel}”后只能连接工艺、装配或发货节点`
    }
    if (hasPath(adjacency, target.id, source.id)) return '批量连接会形成流程环路'
    return null
  }

  function hasPath(adjacency: Map<string, Set<string>>, start: string, goal: string) {
    const queue = [start]
    const visited = new Set<string>()
    while (queue.length) {
      const current = queue.shift()!
      if (current === goal) return true
      if (visited.has(current)) continue
      visited.add(current)
      queue.push(...(adjacency.get(current) ?? []))
    }
    return false
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
        : [{ text: '自动连接', callback: () => autoConnectSelectedNodes(lf) }],
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
    panElement.addEventListener('pointerdown', handleMiddlePanStart, true)
    panElement.addEventListener('pointerdown', handleSelectionStart, true)
    panElement.addEventListener('auxclick', preventMiddleAuxClick)
    panElement.addEventListener('click', handleOverviewClick, true)
    document.addEventListener('pointermove', handleMiddlePanMove)
    document.addEventListener('pointermove', handleSelectionMove)
    document.addEventListener('pointerup', handleMiddlePanEnd)
    document.addEventListener('pointerup', handleSelectionEnd)
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
    panElement?.removeEventListener('pointerdown', handleMiddlePanStart, true)
    panElement?.removeEventListener('pointerdown', handleSelectionStart, true)
    panElement?.removeEventListener('auxclick', preventMiddleAuxClick)
    panElement?.removeEventListener('click', handleOverviewClick, true)
    document.removeEventListener('pointermove', handleMiddlePanMove)
    document.removeEventListener('pointermove', handleSelectionMove)
    document.removeEventListener('pointerup', handleMiddlePanEnd)
    document.removeEventListener('pointerup', handleSelectionEnd)
    selectionBox?.remove()
    selectionBox = null
    selectionStart = null
    panElement = null
    middlePanPoint = null
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
