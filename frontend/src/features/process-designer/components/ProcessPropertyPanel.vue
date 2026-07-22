<script setup lang="ts">
import type { FlowEdge, FlowNode } from '../domain/types'
import type { ProcedureOption } from '@/api/organization'

defineProps<{
  node: FlowNode | null
  edge: FlowEdge | null
  procedures: ProcedureOption[]
  readonly?: boolean
}>()
const emit = defineEmits<{
  updateAssembly: [label: string, output_name: string, output_pcs: number]
  updateProcess: [label: string, process_code: string]
  updateProcedure: [procedure_id: number]
}>()
</script>

<template>
  <aside class="property-panel">
    <template v-if="node?.type === 'process'">
      <h3>工序节点</h3>
      <label>显示名称</label>
      <ElInput :model-value="node.label" :disabled="readonly" @change="emit('updateProcess', $event, node.process_code)" />
      <label>工序编码</label>
      <ElInput :model-value="node.process_code" :disabled="readonly" @change="emit('updateProcess', node.label, $event)" />
      <label>关联工艺</label>
      <ElSelect
        :model-value="node.procedure_id"
        placement="top-start"
        :fallback-placements="['top-start', 'top-end']"
        :disabled="readonly"
        placeholder="选择工艺"
        @update:model-value="emit('updateProcedure', $event)"
      >
        <ElOption
          v-for="item in procedures"
          :key="item.id"
          :label="`${item.procedure_name}${item.procedure_type === 'purchase_receipt' ? '（外购）' : ''}`"
          :value="item.id"
        />
      </ElSelect>
    </template>
    <template v-else-if="node?.type === 'qc'">
      <h3>QC节点</h3>
      <p>合格数量由QC决定何时放行到下一流程节点；返工数量返回原工单。</p>
    </template>
    <template v-else-if="node?.type === 'shipping'">
      <h3>发货节点</h3>
      <p>流程终点。产品经QC出货后离开生产系统。</p>
    </template>
    <template v-else-if="node?.type === 'assembly'">
      <h3>装配节点</h3>
      <label>显示名称</label>
      <ElInput :model-value="node.label" :disabled="readonly" @change="emit('updateAssembly', $event, node.output_name, node.output_pcs)" />
      <label>装配体名称</label>
      <ElInput :model-value="node.output_name" disabled placeholder="根据输入配件自动生成" />
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
.property-panel { padding: 16px; border-left: 1px solid var(--erp-border); background: #f8fafc; }
h3 { margin: 0 0 12px; font-size: 14px; }
label { display: block; margin: 13px 0 5px; color: var(--el-text-color-secondary); font-size: 12px; }
p { margin: 0 0 12px; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.5; }
</style>
