<script setup lang="ts">
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
      <div ref="container" class="production-flow-viewer" />
      <el-popover
        :visible="popoverVisible"
        placement="top"
        :width="320"
        trigger="click"
        popper-class="production-node-progress-popover"
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
      <div class="display-controls" aria-label="节点显示大小">
        <div class="display-control-group">
          <span>字体</span>
          <button type="button" aria-label="缩小字体" title="缩小字体" @click="changeFontSize(-1)">−</button>
          <button type="button" aria-label="放大字体" title="放大字体" @click="changeFontSize(1)">＋</button>
        </div>
        <div class="display-control-group">
          <span>节点</span>
          <button type="button" aria-label="缩小节点" title="缩小节点" @click="changeNodeSize(-0.1)">−</button>
          <button type="button" aria-label="放大节点" title="放大节点" @click="changeNodeSize(0.1)">＋</button>
        </div>
        <div class="display-control-group">
          <span>连线</span>
          <button type="button" aria-label="变细连线" title="变细连线" @click="changeEdgeWidth(-1)">−</button>
          <button type="button" aria-label="加粗连线" title="加粗连线" @click="changeEdgeWidth(1)">＋</button>
        </div>
      </div>
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
  border-color: var(--md-outline-variant);
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
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-lowest);
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
.display-controls { position: absolute; z-index: 10; top: 78px; right: 15px; display: flex; gap: 6px; padding: 6px; border-radius: 8px; background: color-mix(in srgb, var(--md-surface-container-lowest) 88%, transparent); box-shadow: 0 1px 8px rgb(0 0 0 / 12%); }
.display-control-group { display: flex; align-items: center; gap: 4px; padding-left: 6px; color: var(--el-text-color-secondary); font-size: 12px; }
.display-control-group + .display-control-group { margin-left: 2px; padding-left: 8px; border-left: 1px solid var(--md-outline-variant); }
.display-controls button { width: 32px; height: 32px; padding: 0; border: 1px solid var(--md-outline-variant); border-radius: 7px; color: var(--el-text-color-primary); background: var(--md-surface-container-lowest); cursor: pointer; font-size: 16px; }
.display-controls button:hover { color: var(--el-color-primary); border-color: var(--el-color-primary); }
@media (max-width: 760px) {
  .production-flow-legend { gap: 8px 12px; }
  .production-flow-viewer { height: clamp(420px, 65vh, 560px); }
}
</style>
