<script setup lang="ts">
import FlowDisplayControls from './FlowDisplayControls.vue'
import '@logicflow/core/es/index.css'
import '@logicflow/extension/lib/style/index.css'
import { ref } from 'vue'
import type { ProcessFlow } from './types'
import type { ProductionEdgeStat, ProductionNodeStat } from './productionProgress'
import { useProductionFlowCanvas } from './useProductionFlowCanvas'
import ProductionNodeProgressDetails from './ProductionNodeProgressDetails.vue'

const props = defineProps<{
  flow: ProcessFlow
  stats: ProductionNodeStat[]
  edgeStats: ProductionEdgeStat[]
  workshopDepartmentCodes?: Readonly<Record<number, string>>
}>()
const container = ref<HTMLDivElement>()
const popoverAnchor = ref<HTMLElement>()
const {
  changeEdgeWidth,
  changeFontSize,
  changeNodeSize,
  handlePopoverVisibleChange,
  popoverVisible,
  selectedNodeLabel,
  selectedNodeStat,
  selectedNodeType,
} = useProductionFlowCanvas(container, popoverAnchor, {
  flow: () => props.flow,
  stats: () => props.stats,
  edgeStats: () => props.edgeStats,
  workshopDepartmentCodes: () => props.workshopDepartmentCodes,
})

</script>

<template>
  <div class="production-flow-viewer-wrap">
    <div class="production-flow-legend">
      <span><i class="legend-line pending" />未开始</span>
      <span><i class="legend-line active" />进行中</span>
      <span><i class="legend-line done" />已流转</span>
    </div>
    <div class="production-flow-canvas-shell">
      <FlowDisplayControls show-edge-width @font-size="changeFontSize" @node-size="changeNodeSize" @edge-width="changeEdgeWidth" />
      <div ref="container" class="production-flow-viewer" />
      <el-popover
        :visible="popoverVisible"
        placement="top"
        :width="320"
        trigger="click"
        popper-class="production-node-progress-popover"
        :popper-style="{ maxWidth: 'calc(100vw - 24px)' }"
        :fallback-placements="['top', 'right', 'bottom', 'left']"
        @update:visible="handlePopoverVisibleChange"
      >
        <template #reference>
          <span ref="popoverAnchor" class="node-popover-anchor" />
        </template>
        <ProductionNodeProgressDetails
          :label="selectedNodeLabel"
          :type="selectedNodeType"
          :stat="selectedNodeStat"
        />
      </el-popover>
    </div>
  </div>
</template>

<style scoped>
.production-flow-viewer-wrap {
  width: 100%;
}

.production-flow-canvas-shell {
  position: relative;
  min-width: 0;
  border: 1px solid var(--erp-border);
  border-radius: var(--erp-radius);
  overflow: hidden;
}

.node-popover-anchor {
  position: fixed;
  z-index: -1;
  width: 1px;
  height: 1px;
  pointer-events: none;
}

.production-flow-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.production-flow-legend span {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.legend-line {
  display: inline-block;
  width: 28px;
  height: 0;
  border-top: 3px solid;
}

.legend-line.pending {
  border-color: var(--erp-border-strong);
  border-style: dashed;
}

.legend-line.active {
  border-color: var(--erp-warning);
  border-style: dashed;
}

.legend-line.done {
  border-color: var(--erp-success);
}

.production-flow-viewer {
  width: 100%;
  height: clamp(560px, 70vh, 840px);
  background: var(--erp-surface);
  cursor: grab;
}
.production-flow-viewer :deep(.lf-node-content text) { pointer-events: none; user-select: none; cursor: inherit; font-size: var(--process-node-font-size, 13px); font-weight: 700; text-rendering: geometricPrecision; }
.production-flow-viewer :deep(.lf-edge > g:first-child polyline) { stroke-width: var(--process-edge-width, 3px) !important; }
.production-flow-viewer :deep(.lf-edge path),
.production-flow-viewer :deep(.lf-edge polyline),
.production-flow-viewer :deep(.lf-node-content > g > rect),
.production-flow-viewer :deep(.lf-node-content > g > polygon) { vector-effect: non-scaling-stroke; }
.production-flow-viewer :deep(.lf-anchor) { pointer-events: all; transform: scale(var(--process-node-anchor-scale, 1)); transform-box: fill-box; transform-origin: center; }
.production-flow-viewer :deep(.lf-node) { cursor: pointer; }
.production-flow-viewer.is-canvas-panning { cursor: grabbing; }
@media (max-width: 760px) {
  .production-flow-legend { gap: 8px 12px; }
  .production-flow-viewer { height: clamp(420px, 65vh, 560px); }
}
</style>
