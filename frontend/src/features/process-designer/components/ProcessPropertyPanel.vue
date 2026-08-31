<script setup lang="ts">
import type { FlowEdge, FlowNode } from '../domain/types'
import type { WorkshopRouteOption } from '@/api/organization'

const props = defineProps<{
  node: FlowNode | null
  edge: FlowEdge | null
  workshops: WorkshopRouteOption[]
  readonly?: boolean
}>()
const emit = defineEmits<{
  updateAssembly: [label: string, output_name: string, output_pcs: number]
}>()

function workshopName(node: FlowNode | null) {
  if (!node || (node.type !== 'process' && node.type !== 'assembly')) return ''
  return props.workshops.find(item => item.id === node.workshop_id)?.workshop_name || node.label
}
</script>

<template>
  <aside class="property-panel">
    <template v-if="node?.type === 'process'">
      <h3>工序节点</h3>
      <label>车间</label>
      <ElInput :model-value="workshopName(node)" disabled />
      <p>具体加工工艺由该车间开工单时选择。</p>
    </template>
    <template v-else-if="node?.type === 'qc'">
      <h3>QC节点</h3>
      <p>合格数量由QC决定何时放行到下一流程节点；返工数量返回原工单。</p>
    </template>
    <template v-else-if="node?.type === 'supplier_processing'">
      <h3>委外加工节点</h3>
      <p>由业务部在生产计划确认后填写供应商和加工工艺并创建委外工单。</p>
      <p>该节点必须直接连接在配件之后，并直接连接到 QC。</p>
    </template>
    <template v-else-if="node?.type === 'finished_inbound'">
      <h3>入库节点</h3>
      <p>流程终点。产品经 QC 放行后进入成品部待入库，由成品部确认入库。</p>
    </template>
    <template v-else-if="node?.type === 'assembly'">
      <h3>装配节点</h3>
      <label>车间</label>
      <ElInput :model-value="workshopName(node)" disabled />
      <label>装配体名称</label>
      <ElInput :model-value="node.output_name" disabled placeholder="根据输入配件自动生成" />
      <label>系统编号</label>
      <ElInput :model-value="node.assembly_code || '保存流程后生成'" disabled />
      <label>每件产品所需装配体数量</label>
      <ElInputNumber :model-value="node.output_pcs" :disabled="readonly" :min="1" @change="emit('updateAssembly', node.label, node.output_name, $event || 1)" />
    </template>
    <template v-else-if="node?.type === 'part'">
      <h3>配件节点</h3>
      <p>{{ node.label }}</p>
      <p>{{ node.part_no }}</p>
    </template>
    <template v-else-if="edge">
      <h3>连线属性</h3>
      <p>宏观工艺连线按正常路线流转。</p>
    </template>
  </aside>
</template>

<style scoped>
.property-panel { padding: 16px; border-left: 1px solid var(--md-outline-variant); background: var(--md-surface-container-low); }
h3 { margin: 0 0 12px; font-size: 14px; }
label { display: block; margin: 13px 0 5px; color: var(--el-text-color-secondary); font-size: 12px; }
p { margin: 0 0 12px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
</style>
