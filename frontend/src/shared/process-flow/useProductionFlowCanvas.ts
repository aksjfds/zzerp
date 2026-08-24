import { nextTick, onBeforeUnmount, onMounted, watch, type Ref } from 'vue'
import type LogicFlow from '@logicflow/core'
import { toLogicFlowData } from './adapter'
import { updateProcessCanvasScale } from './nodeTextScale'
import { installProductionFlowPan } from './productionFlowInteractions'
import { createProductionFlowInstance } from './productionFlowLifecycle'
import type { ProductionEdgeStat, ProductionNodeStat } from './productionProgress'
import type { ProcessFlow } from './types'
import { useProductionFlowDisplay } from './useProductionFlowDisplay'
import { useProductionFlowPopover } from './useProductionFlowPopover'
import {
  buildProductionFlow,
  shouldAnimateEdge,
  withProductionEdgeStyle,
} from './productionViewerModel'

type FlowCanvasSource = {
  flow: () => ProcessFlow
  stats: () => ProductionNodeStat[]
  edgeStats: () => ProductionEdgeStat[]
  workshopDepartmentCodes: () => Readonly<Record<number, string>> | undefined
}

export function useProductionFlowCanvas(
  container: Ref<HTMLDivElement | undefined>,
  popoverAnchor: Ref<HTMLElement | undefined>,
  source: FlowCanvasSource,
) {
  let instance: LogicFlow | null = null
  let resizeObserver: ResizeObserver | null = null
  let resizeFrame: number | null = null
  let fitFrame: number | null = null
  let removePanListeners: (() => void) | null = null

  const popover = useProductionFlowPopover(
    container,
    popoverAnchor,
    () => instance,
    source.flow,
    source.stats,
  )
  const display = useProductionFlowDisplay(container, () => instance)

  function fitFlowToView() {
    if (fitFrame !== null) cancelAnimationFrame(fitFrame)
    fitFrame = requestAnimationFrame(() => {
      fitFrame = null
      if (!instance || !container.value) return
      instance.resize(container.value.clientWidth, container.value.clientHeight)
      instance.fitView(48, 48)
      updateProcessCanvasScale(
        container.value,
        instance.graphModel.transformModel.SCALE_X,
      )
    })
  }

  function handleOverviewClick(event: MouseEvent) {
    const target = event.target
    const controlItem = target instanceof Element
      ? target.closest('.lf-control-item')
      : null
    if (!controlItem?.querySelector('.lf-control-fit')) return
    event.preventDefault()
    event.stopPropagation()
    fitFlowToView()
  }

  function progressMaps() {
    return {
      nodes: new Map(source.stats().map(node => [node.flow_node_id, node])),
      edges: new Map(source.edgeStats().map(edge => [edge.flow_edge_id, edge])),
    }
  }

  function updateProgressStyles() {
    if (!instance) return
    popover.refreshSelectedStat()
    const flow = source.flow()
    const progress = progressMaps()
    const styledData = withProductionEdgeStyle(
      toLogicFlowData(buildProductionFlow(flow), {
        workshopDepartmentCode: workshopId => source.workshopDepartmentCodes()?.[workshopId],
      }),
      flow,
      progress.nodes,
      progress.edges,
    )
    styledData.edges?.forEach((edge) => {
      if (edge.id && edge.properties) instance?.setProperties(edge.id, edge.properties)
    })
    flow.edges.forEach((edge) => {
      if (shouldAnimateEdge(edge, progress.nodes, progress.edges)) {
        instance?.openEdgeAnimation(edge.id)
      } else {
        instance?.closeEdgeAnimation(edge.id)
      }
    })
  }

  function renderTopology() {
    if (!instance) return
    const flow = source.flow()
    const progress = progressMaps()
    instance.renderRawData(withProductionEdgeStyle(
      toLogicFlowData(buildProductionFlow(flow), {
        workshopDepartmentCode: workshopId => source.workshopDepartmentCodes()?.[workshopId],
      }),
      flow,
      progress.nodes,
      progress.edges,
    ))
    display.applyDisplaySettings()
    requestAnimationFrame(() => {
      updateProgressStyles()
      fitFlowToView()
    })
  }

  function resizeCanvas() {
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = null
      if (!instance || !container.value) return
      instance.resize(container.value.clientWidth, container.value.clientHeight)
    })
  }

  onMounted(async () => {
    await nextTick()
    if (!container.value) return
    instance = createProductionFlowInstance(container.value)
    display.applyDisplaySettings()
    removePanListeners = installProductionFlowPan(
      container,
      () => instance,
      popover.closeNodeProgress,
    )
    container.value.addEventListener('click', handleOverviewClick, true)
    instance.on('graph:transform', ({ transform }) => {
      popover.closeNodeProgress()
      if (container.value) updateProcessCanvasScale(container.value, transform.SCALE_X)
    })
    instance.on('node:click', ({ data, e }) => (
      popover.showNodeProgress(data.id, e as MouseEvent | undefined)
    ))
    instance.on('blank:click', popover.closeNodeProgress)
    renderTopology()
    resizeObserver = new ResizeObserver(resizeCanvas)
    resizeObserver.observe(container.value)
  })

  watch(
    () => [source.flow(), source.workshopDepartmentCodes()],
    renderTopology,
    { deep: true },
  )
  watch(
    () => [source.stats(), source.edgeStats()],
    updateProgressStyles,
    { deep: true },
  )

  onBeforeUnmount(() => {
    container.value?.removeEventListener('click', handleOverviewClick, true)
    removePanListeners?.()
    resizeObserver?.disconnect()
    if (resizeFrame !== null) cancelAnimationFrame(resizeFrame)
    if (fitFrame !== null) cancelAnimationFrame(fitFrame)
    instance?.destroy()
    instance = null
  })

  return {
    changeEdgeWidth: display.changeEdgeWidth,
    changeFontSize: display.changeFontSize,
    changeNodeSize: display.changeNodeSize,
    handlePopoverVisibleChange: popover.handlePopoverVisibleChange,
    popoverVisible: popover.popoverVisible,
    selectedNodeLabel: popover.selectedNodeLabel,
    selectedNodeStat: popover.selectedNodeStat,
    selectedNodeType: popover.selectedNodeType,
  }
}
