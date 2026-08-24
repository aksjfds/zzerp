import type LogicFlow from '@logicflow/core'
import { nextTick, ref, type Ref } from 'vue'
import type { ProductionNodeStat } from './productionProgress'
import type { FlowNodeType, ProcessFlow } from './types'

export function useProductionFlowPopover(
  container: Ref<HTMLDivElement | undefined>,
  anchor: Ref<HTMLElement | undefined>,
  getInstance: () => LogicFlow | null,
  getFlow: () => ProcessFlow,
  getStats: () => ProductionNodeStat[],
) {
  const popoverVisible = ref(false)
  const selectedNodeLabel = ref('')
  const selectedNodeType = ref<FlowNodeType>()
  const selectedNodeStat = ref<ProductionNodeStat | null>(null)
  const selectedNodeId = ref<string>()

  function closeNodeProgress() {
    popoverVisible.value = false
    selectedNodeId.value = undefined
    getInstance()?.clearSelectElements()
  }

  function handlePopoverVisibleChange(visible: boolean) {
    popoverVisible.value = visible
    if (!visible) closeNodeProgress()
  }

  function showNodeProgress(nodeId: string, event?: MouseEvent | PointerEvent) {
    const node = getFlow().nodes.find(item => item.id === nodeId)
    if (!node || !anchor.value) return
    closeNodeProgress()
    selectedNodeLabel.value = node.label
    selectedNodeType.value = node.type
    selectedNodeId.value = nodeId
    selectedNodeStat.value = getStats().find(item => item.flow_node_id === nodeId) ?? null
    const nodeElement = container.value?.querySelector(`[data-id="${CSS.escape(nodeId)}"]`)
    const rect = nodeElement?.getBoundingClientRect()
    anchor.value.style.left = `${event?.clientX ?? (rect ? rect.left + rect.width / 2 : 0)}px`
    anchor.value.style.top = `${event?.clientY ?? (rect ? rect.top + rect.height / 2 : 0)}px`
    void nextTick(() => {
      getInstance()?.selectElementById(nodeId)
      popoverVisible.value = true
    })
  }

  function refreshSelectedStat() {
    if (!selectedNodeId.value) return
    selectedNodeStat.value = getStats().find(
      item => item.flow_node_id === selectedNodeId.value,
    ) ?? null
  }

  return {
    closeNodeProgress,
    handlePopoverVisibleChange,
    popoverVisible,
    refreshSelectedStat,
    selectedNodeLabel,
    selectedNodeStat,
    selectedNodeType,
    showNodeProgress,
  }
}
