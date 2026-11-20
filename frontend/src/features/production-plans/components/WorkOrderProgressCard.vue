<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { PLAN_PERMISSIONS } from '@/permission/constants'
import type { DepartmentWorkOrder, WorkOrderSchedule } from '../api/plans'
import WorkOrderScheduleCell from './WorkOrderScheduleCell.vue'
const props = defineProps<{ order: DepartmentWorkOrder; compact?: boolean; departmentView?: boolean; schedulingOrders?: WorkOrderSchedule[] }>()
defineEmits<{ ledger: [order: DepartmentWorkOrder]; scheduled: [updates: WorkOrderSchedule[]] }>()
const auth = useAuthStore()
const progress = computed(() => {
  const issued = BigInt(props.order.issued_quantity), target = BigInt(props.order.task_quantity)
  return Number((issued < target ? issued : target) * 10000n / target) / 100
})
</script>
<template>
  <article class="work-card" :class="{ 'is-row': compact || departmentView }">
    <header v-if="!departmentView"><strong>{{ order.department_name }}</strong></header>
    <div v-if="!compact" class="identity"><p class="product">{{ order.factory_code }} · {{ order.product_name }}</p>
    <p class="material">{{ order.part_no }} · {{ order.part_name }}</p>
    <p class="reference">订单 {{ order.order_no }}</p></div>
    <div class="output-progress"><div class="progress-caption"><span>出料进度</span><strong>{{ order.issued_quantity }} <small>/ {{ order.task_quantity }}</small></strong></div><ElProgress :percentage="progress" :show-text="false" :stroke-width="10" :color="progress >= 100 ? 'var(--erp-success)' : 'var(--erp-primary)'" :aria-label="`累计出料 ${order.issued_quantity}，任务数量 ${order.task_quantity}`" /></div>
    <footer><WorkOrderScheduleCell :order="order" :orders="schedulingOrders" :editable="!auth.user?.department_code && auth.hasPermission(PLAN_PERMISSIONS.edit) && order.plan_status === 'confirmed'" @saved="$emit('scheduled', $event)" /><ElButton link type="primary" @click="$emit('ledger', order)">查看流水</ElButton></footer>
  </article>
</template>
<style scoped>
.work-card { min-width: 0; padding: 20px; border: 1px solid var(--erp-border); border-top: 3px solid var(--erp-primary); border-radius: 10px; background: var(--erp-surface); }
header, footer { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
header strong { font-size: 17px; } p { margin: 10px 0; overflow-wrap: anywhere; }
.product { font-weight: 600; }.material { color: var(--erp-text-secondary); }.reference { font-size: 13px; color: var(--erp-text-secondary); }
.output-progress { min-width: 0; margin: 18px 0; }.progress-caption { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 10px; }.progress-caption > span { font-size: 12px; color: var(--erp-text-secondary); }.progress-caption strong { font-size: 20px; font-variant-numeric: tabular-nums; }.progress-caption small { font-size: 13px; font-weight: 500; color: var(--erp-text-secondary); }
.output-progress :deep(.el-progress-bar__outer) { background: var(--erp-primary-soft); }
footer { border-top: 1px solid var(--erp-border); padding-top: 12px; font-size: 13px; }
footer :deep(.schedule-cell) { flex-wrap: wrap; }
.work-card.is-row { display: grid; grid-template-columns: minmax(160px,1fr) minmax(180px,1fr) minmax(320px,1.8fr); align-items: center; gap: 16px; padding: 12px 16px; border-top-width: 1px; border-left: 3px solid var(--erp-primary); }
.is-row header { justify-content: flex-start; }.is-row header strong { font-size: 16px; }
.is-row .identity p { margin: 0 0 4px; }
.is-row .output-progress { margin: 0; }
.is-row footer { border: 0; padding: 0; }
@media (max-width: 900px) { .work-card.is-row { grid-template-columns: minmax(0,1fr) minmax(0,2fr); }.is-row footer { grid-column: 1 / -1; } }
@media (max-width: 520px) { .work-card.is-row { grid-template-columns: minmax(0,1fr); }.is-row footer { justify-content: space-between; } }
</style>
