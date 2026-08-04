import { nextTick, onBeforeUnmount, onMounted, shallowRef, type Ref } from 'vue'
import LogicFlow from '@logicflow/core'
import { Control, Menu } from '@logicflow/extension'
import { registerProcessNodes } from '@/shared/process-flow/registerNodes'
import { fromLogicFlowData, toLogicFlowData } from '@/shared/process-flow/adapter'
import type { FlowEdge, FlowNode, ProcessFlow } from '../domain/types'

type Callbacks = {
  initialFlow: () => ProcessFlow
  readonly?: () => boolean
  onChange: (flow: ProcessFlow) => void
  onConnectionError: (message: string) => void
  onSelectEdge: (edge: FlowEdge | null) => void
  onSelectNode: (node: FlowNode | null) => void
}

export function useLogicFlowInstance(container: Ref<HTMLDivElement | undefined>, callbacks: Callbacks) {
  const instance = shallowRef<LogicFlow | null>(null)
  let resizeObserver: ResizeObserver | null = null
  let resizeFrame: number | null = null

  function fitToContainer() {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = null
      const element = container.value
      const lf = instance.value
      if (!element || !lf) return
      lf.resize(element.clientWidth, element.clientHeight)
      if (currentFlow().nodes.length) lf.fitView(24, 24)
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
      nodeTextDraggable: !readonly,
      nodeTextEdit: !readonly,
      stopMoveGraph: false,
      stopScrollGraph: readonly,
      stopZoomGraph: readonly,
      textDraggable: !readonly,
      textEdit: !readonly,
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
    instance.value?.renderRawData(toLogicFlowData(flow))
  }

  onMounted(async () => {
    await nextTick()
    if (!container.value) return
    const lf = new LogicFlow({
      container: container.value,
      grid: { size: 20, visible: true },
      edgeType: 'polyline',
      keyboard: { enabled: true },
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
      'node:add,node:delete,edge:delete,node:drop,node:dragend,node:rotate,node:resize,node:properties-change,edge:adjust,edge:exchange-node,text:update',
      emitChange,
    )
    lf.on('connection:not-allowed', ({ msg }) => {
      callbacks.onConnectionError(msg || '该连线不符合流程规则')
    })
    renderFlow(callbacks.initialFlow())
    resizeObserver = new ResizeObserver(fitToContainer)
    resizeObserver.observe(container.value)
    fitToContainer()
  })

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    resizeObserver = null
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    resizeFrame = null
    instance.value?.destroy()
    instance.value = null
  })

  return { currentFlow, emitChange, instance, renderFlow, setReadonly }
}
