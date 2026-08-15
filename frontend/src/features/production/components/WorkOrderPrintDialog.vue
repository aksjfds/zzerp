<script setup lang="ts">
import { computed } from 'vue'
import type { WorkOrder } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: WorkOrder
}>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const typeLabel = computed(() => ({
  tag: '生产标记工单',
  purchase_receipt: '外购入库工单',
  assembly: '装配工单',
}[props.item?.work_order_type || 'tag']))
const statusLabel = computed(() => ({
  open: '进行中',
  closed: '已结单',
  cancelled: '已取消',
}[props.item?.status || 'open']))

function print() {
  window.print()
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    title="打印工单"
    width="min(820px, 94vw)"
    append-to-body
    class="work-order-print-dialog"
    :modal-class="modelValue ? 'work-order-print-overlay work-order-print-overlay--active' : 'work-order-print-overlay'"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <article v-if="item" class="print-sheet">
      <header>
        <div>
          <p>ZZ ERP</p>
          <h1>{{ typeLabel }}</h1>
        </div>
        <div class="order-number">
          <span>工单编号</span>
          <strong>{{ item.work_order_no }}</strong>
        </div>
      </header>

      <table>
        <tbody>
          <tr><th>客户订单</th><td>{{ item.customer_order_no }}</td><th>工单状态</th><td>{{ statusLabel }}</td></tr>
          <tr><th>配件编号</th><td>{{ item.part_no }}</td><th>配件名称</th><td>{{ item.part_name }}</td></tr>
          <tr><th>工单内容</th><td>{{ item.work_order_name }}</td><th>{{ item.work_order_type === 'assembly' ? '对应产品数 / 装配体数' : '工单数量' }}</th><td class="quantity">{{ item.work_order_type === 'assembly' ? `${item.quantity} / ${item.output_quantity}` : item.quantity }}</td></tr>
          <tr><th>执行工人</th><td>{{ item.worker_name || '未分配' }}</td><th>创建时间</th><td>{{ item.created_at }}</td></tr>
          <tr><th>备注</th><td colspan="3" class="remark">{{ item.remark || '无' }}</td></tr>
        </tbody>
      </table>

      <section class="progress-section">
        <h2>执行记录</h2>
        <div class="progress-grid">
          <div><span>{{ item.work_order_type === 'assembly' ? '已提交产品数' : '已提交' }}</span><strong>{{ item.submitted_quantity }}</strong></div>
          <div><span>{{ item.work_order_type === 'assembly' ? '装配/返工中' : '加工中' }}</span><strong>{{ item.work_order_type === 'assembly' ? item.processing_output_quantity : item.processing_quantity }}</strong></div>
          <div><span>待质检</span><strong>{{ item.pending_qc_quantity }}</strong></div>
          <div><span>合格</span><strong>{{ item.work_order_type === 'assembly' ? item.qualified_output_quantity : item.qualified_quantity }}</strong></div>
          <div><span>报废</span><strong>{{ item.scrap_quantity }}</strong></div>
          <div><span>遗失</span><strong>{{ item.lost_quantity }}</strong></div>
        </div>
      </section>

      <footer>
        <div>制单：________________</div>
        <div>领单：________________</div>
        <div>审核：________________</div>
      </footer>
    </article>
    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
      <ElButton type="primary" @click="print">打印</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.print-sheet { padding: 8px 10px 20px; color: #111827; background: #fff; }
.print-sheet header { display: flex; justify-content: space-between; align-items: flex-start; padding-bottom: 18px; border-bottom: 2px solid #111827; }
.print-sheet header p { margin: 0 0 4px; font-weight: 700; letter-spacing: 1px; }
.print-sheet h1 { margin: 0; font-size: 25px; }
.order-number { display: grid; gap: 5px; text-align: right; }
.order-number span { color: #6b7280; font-size: 12px; }
.order-number strong { font-size: 18px; }
table { width: 100%; margin-top: 18px; border-collapse: collapse; table-layout: fixed; }
th, td { padding: 12px 10px; border: 1px solid #374151; text-align: left; overflow-wrap: anywhere; }
th { width: 15%; background: #f3f4f6; font-size: 13px; }
td { width: 35%; }
.quantity { font-size: 20px; font-weight: 800; }
.remark { min-height: 64px; white-space: pre-wrap; }
.progress-section { margin-top: 20px; }
.progress-section h2 { margin: 0 0 10px; font-size: 16px; }
.progress-grid { display: grid; grid-template-columns: repeat(6, 1fr); border: 1px solid #374151; }
.progress-grid div { display: grid; gap: 7px; padding: 10px; text-align: center; }
.progress-grid div + div { border-left: 1px solid #374151; }
.progress-grid span { color: #6b7280; font-size: 12px; }
.progress-grid strong { font-size: 18px; }
.print-sheet footer { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 52px; }

@media screen and (max-width: 620px) {
  .print-sheet header { align-items: flex-start; flex-direction: column; gap: 12px; }
  .order-number { text-align: left; }
  th, td { padding: 8px 6px; font-size: 12px; }
  .progress-grid { grid-template-columns: repeat(2, 1fr); }
  .progress-grid div { border: 0; border-bottom: 1px solid #374151; }
  .progress-grid div + div { border-left: 0; }
  .print-sheet footer { grid-template-columns: 1fr; gap: 16px; margin-top: 32px; }
}

@media print {
  :global(body > *) { display: none !important; }
  :global(body > .work-order-print-overlay--active) {
    display: block !important;
    position: static !important;
    width: auto !important;
    height: auto !important;
    overflow: visible !important;
    background: transparent !important;
  }
  :global(.work-order-print-overlay .el-overlay-dialog) {
    position: static !important;
    overflow: visible !important;
  }
  .print-sheet { position: static; width: auto; padding: 0; }
  :global(.work-order-print-dialog .el-dialog__header),
  :global(.work-order-print-dialog .el-dialog__footer) { display: none !important; }
  :global(.work-order-print-dialog.el-dialog) { width: auto !important; margin: 0 !important; padding: 0 !important; border: 0 !important; border-radius: 0 !important; background: #fff !important; box-shadow: none !important; }
  :global(.work-order-print-dialog .el-dialog__body) { padding: 0 !important; }
}

@page { size: A4 portrait; margin: 12mm; }
</style>
