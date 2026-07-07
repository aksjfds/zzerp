<script setup lang="ts">
import '@logicflow/core/es/index.css'
import '@logicflow/extension/lib/style/index.css'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import LogicFlow from '@logicflow/core'
import { Control } from '@logicflow/extension'
import { registerProcessNodes } from '@/features/process-designer/logicflow/registerNodes'
import { toLogicFlowData } from '@/features/process-designer/logicflow/adapter'
import type { ProcessFlow } from '@/features/process-designer/domain/types'
import type { ProductionNodeStat } from '../domain/types'

const props = defineProps<{
  flow: ProcessFlow
  stats: ProductionNodeStat[]
}>()
const container = ref<HTMLDivElement>()
let instance: LogicFlow | null = null

function nodeLabel(label: string, stat?: ProductionNodeStat): string {
  if (!stat) return `${label}\n入0 出0`
  if (stat.node_type === 'assembly') {
    return `${label}\n装配${stat.transferred_quantity} 产出${stat.output_quantity}`
  }
  if (stat.node_type === 'part') {
    return `${label}\n投入${stat.entered_quantity} 转出${stat.transferred_quantity}`
  }
  if (stat.node_type === 'qc') {
    return `${label}\n入${stat.entered_quantity} 出${stat.transferred_quantity} 异常${stat.abnormal_quantity}`
  }
  return `${label}\n入${stat.entered_quantity} 出${stat.transferred_quantity} 现${stat.current_quantity}`
}

function render() {
  if (!instance) return
  const status = new Map(props.stats.map(node => [node.flow_node_id, node]))
  const flow: ProcessFlow = {
    ...props.flow,
    nodes: props.flow.nodes
      .map(node => ({
        ...node,
        label: nodeLabel(node.label, status.get(node.id)),
      })),
    edges: props.flow.edges,
  }
  instance.renderRawData(toLogicFlowData(flow))
  requestAnimationFrame(() => instance?.fitView(24, 24))
}

onMounted(async () => {
  await nextTick()
  if (!container.value) return
  instance = new LogicFlow({
    container: container.value,
    isSilentMode: true,
    grid: false,
    edgeType: 'polyline',
    stopZoomGraph: false,
    stopScrollGraph: false,
    stopMoveGraph: false,
    plugins: [Control],
  })
  registerProcessNodes(instance)
  render()
})

watch(() => [props.flow, props.stats], render, { deep: true })
onBeforeUnmount(() => {
  instance?.destroy()
  instance = null
})
</script>

<template>
  <div ref="container" class="production-flow-viewer" />
</template>

<style scoped>
.production-flow-viewer { width: 100%; height: clamp(480px, 62vh, 720px); border: 1px solid var(--erp-border); border-radius: 8px; background: #fff; }
.assembly-inputs { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 8px; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
