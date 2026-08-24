import type LogicFlow from '@logicflow/core'
import type { Ref } from 'vue'
import {
  applyProcessNodeScale,
  PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY,
  PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY,
  PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY,
  storedProcessFlowNumber,
} from './canvasDisplay'

export function useProductionFlowDisplay(
  container: Ref<HTMLDivElement | undefined>,
  getInstance: () => LogicFlow | null,
) {
  let fontSize = storedProcessFlowNumber(PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY, 13, 10)
  let nodeScale = storedProcessFlowNumber(PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY, 1, 0.6)
  let edgeWidth = storedProcessFlowNumber(PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY, 3, 1)

  function applyDisplaySettings() {
    container.value?.style.setProperty('--process-node-font-size', `${fontSize}px`)
    container.value?.style.setProperty('--process-edge-width', `${edgeWidth}px`)
    const instance = getInstance()
    if (instance) applyProcessNodeScale(instance, nodeScale)
  }

  function changeFontSize(delta: number) {
    fontSize = Math.max(10, fontSize + delta)
    localStorage.setItem(PRODUCTION_FLOW_FONT_SIZE_STORAGE_KEY, String(fontSize))
    applyDisplaySettings()
  }

  function changeNodeSize(delta: number) {
    nodeScale = Math.max(0.6, Number((nodeScale + delta).toFixed(2)))
    localStorage.setItem(PRODUCTION_FLOW_NODE_SCALE_STORAGE_KEY, String(nodeScale))
    applyDisplaySettings()
  }

  function changeEdgeWidth(delta: number) {
    edgeWidth = Math.max(1, edgeWidth + delta)
    localStorage.setItem(PRODUCTION_FLOW_EDGE_WIDTH_STORAGE_KEY, String(edgeWidth))
    applyDisplaySettings()
  }

  return {
    applyDisplaySettings,
    changeEdgeWidth,
    changeFontSize,
    changeNodeSize,
  }
}
