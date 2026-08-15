<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  queryProductionProgressItemDetail,
  type DepartmentProductionProgressItem,
  type ProductionProgressItemDetail,
  type ProductionProgressTagCard,
} from '../api/productionProgress'

const props = defineProps<{
  modelValue: boolean
  departmentCode: string
  item: DepartmentProductionProgressItem | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const loading = ref(false)
const detail = ref<ProductionProgressItemDetail | null>(null)

const statusLabels: Record<ProductionProgressTagCard['status'], string> = {
  not_arrived: '未到货',
  ready: '待开工',
  processing: '生产中',
  pending_qc: '待检',
  completed: '已完成',
  exception: '存在异常',
}
const statusTypes: Record<
  ProductionProgressTagCard['status'],
  'info' | 'primary' | 'warning' | 'success' | 'danger'
> = {
  not_arrived: 'info',
  ready: 'primary',
  processing: 'warning',
  pending_qc: 'warning',
  completed: 'success',
  exception: 'danger',
}
const planStatusLabels = {
  draft: '草稿',
  confirmed: '已确认',
  cancelled: '已取消',
}
const workOrderStatusLabels = {
  open: '进行中',
  closed: '已完成',
  cancelled: '已取消',
}

function progressWidth(quantity: number, taskQuantity: number) {
  if (taskQuantity <= 0) return '0%'
  return `${Math.min(Math.max(quantity / taskQuantity * 100, 0), 100)}%`
}

function machiningCompletedQuantity(card: ProductionProgressTagCard) {
  return Math.min(card.completed_quantity, card.task_quantity)
}

function progressSegments(card: ProductionProgressTagCard) {
  let remaining = Math.max(card.task_quantity, 0)
  const take = (quantity: number) => {
    const result = Math.min(Math.max(quantity, 0), remaining)
    remaining -= result
    return result
  }
  const completed = take(machiningCompletedQuantity(card))
  const exception = take(exceptionQuantity(card))
  const submitted = take(card.pending_qc_quantity)
  const processing = take(card.processing_quantity)
  return { completed, exception, submitted, processing }
}

function segmentProgressWidth(
  card: ProductionProgressTagCard,
  segment: keyof ReturnType<typeof progressSegments>,
) {
  return progressWidth(progressSegments(card)[segment], card.task_quantity)
}

function currentProgressQuantity(card: ProductionProgressTagCard) {
  return Object.values(progressSegments(card)).reduce(
    (total, quantity) => total + quantity,
    0,
  )
}

function exceptionQuantity(card: ProductionProgressTagCard) {
  return card.rework_quantity + card.scrap_quantity + card.lost_quantity
}

function isFocused(card: ProductionProgressTagCard) {
  return Boolean(
    props.item?.processing_workshop
    && (
      props.item.flow_node_id
        ? card.flow_node_id === props.item.flow_node_id
        : card.workshop_name === props.item.processing_workshop
    ),
  )
}

function displayWorkshopName(name: string) {
  return name.replace(/车间$/, '') || '—'
}

function workOrderStatusLabel(status: 'open' | 'closed' | 'cancelled') {
  return workOrderStatusLabels[status]
}

async function load() {
  if (!props.item || !props.departmentCode) return
  loading.value = true
  detail.value = null
  try {
    detail.value = await queryProductionProgressItemDetail(
      props.departmentCode,
      props.item.production_plan_item_id,
      props.item.processing_workshop,
      props.item.flow_node_id,
    )
  } catch (error) {
    ElMessage.error(
      getApiErrorDetail(error)?.message || '生产情况加载失败',
    )
  } finally {
    loading.value = false
  }
}

watch(
  () => [
    props.modelValue,
    props.item?.production_plan_item_id,
    props.item?.processing_workshop,
    props.item?.flow_node_id,
  ] as const,
  ([open]) => {
    if (open) void load()
  },
)
</script>

<template>
  <ElDrawer
    v-model="visible"
    title="生产情况"
    size="72%"
    destroy-on-close
    modal-class="production-progress-overlay"
    class="production-progress-drawer"
  >
    <div v-loading="loading" class="drawer-body">
      <template v-if="detail">
        <header class="item-header">
          <div>
            <p class="item-kicker">订单 {{ detail.customer_order_no }}</p>
            <h2>{{ detail.part_no }} · {{ detail.part_name }}</h2>
            <p>{{ detail.factory_code }} · {{ detail.product_name }}</p>
          </div>
          <div class="item-header-meta">
            <ElTag effect="light">{{ planStatusLabels[detail.plan_status] }}</ElTag>
            <strong>计划任务 {{ detail.task_quantity }}</strong>
          </div>
        </header>

        <ElAlert
          type="info"
          :closable="false"
          show-icon
          title="各标记独立统计；同一工单同时加工多个标记时会分别计入对应卡片，卡片数量不能相加。"
        />

        <div v-if="detail.cards.length" class="tag-card-grid">
          <article
            v-for="card in detail.cards"
            :key="card.card_key"
            class="tag-progress-card"
            :class="{ focused: isFocused(card) }"
          >
            <header class="card-header">
              <div>
                <div class="card-title-row">
                  <h3>{{ card.card_name }}</h3>
                  <ElTag
                    v-if="card.card_type !== 'tag'"
                    size="small"
                    type="info"
                    effect="plain"
                  >
                    {{ card.card_type === 'assembly' ? '装配' : card.card_type === 'purchase' ? '外购' : '无标记' }}
                  </ElTag>
                </div>
                <p>
                  {{ card.department_name }} · {{ displayWorkshopName(card.workshop_name) }}
                  · {{ card.procedure_name }}
                </p>
              </div>
              <ElTag :type="statusTypes[card.status]" effect="light">
                {{ statusLabels[card.status] }}
              </ElTag>
            </header>

            <div class="quantity-progress">
              <div
                class="quantity-progress-track"
                role="progressbar"
                :aria-label="`${card.card_name}加工进度`"
                aria-valuemin="0"
                :aria-valuemax="card.task_quantity"
                :aria-valuenow="currentProgressQuantity(card)"
              >
                <span
                  class="quantity-progress-segment completed"
                  :style="{ width: segmentProgressWidth(card, 'completed') }"
                />
                <span
                  class="quantity-progress-segment exception"
                  :style="{ width: segmentProgressWidth(card, 'exception') }"
                />
                <span
                  class="quantity-progress-segment submitted"
                  :style="{ width: segmentProgressWidth(card, 'submitted') }"
                />
                <span
                  class="quantity-progress-segment processing"
                  :style="{ width: segmentProgressWidth(card, 'processing') }"
                />
              </div>
              <div class="quantity-progress-legend">
                <span class="completed">已完成</span>
                <span class="exception">异常</span>
                <span class="submitted">送检中</span>
                <span class="processing">加工中</span>
              </div>
            </div>

            <dl class="card-metrics">
              <div>
                <dt>任务数量</dt>
                <dd>{{ card.task_quantity }}</dd>
              </div>
              <div>
                <dt>加工中</dt>
                <dd>{{ card.processing_quantity }}</dd>
              </div>
              <div>
                <dt>送检中</dt>
                <dd>{{ card.pending_qc_quantity }}</dd>
              </div>
              <div>
                <dt>QC 合格</dt>
                <dd>{{ card.completed_quantity }}</dd>
              </div>
              <div>
                <dt>异常数量</dt>
                <dd :class="{ danger: exceptionQuantity(card) > 0 }">
                  {{ exceptionQuantity(card) }}
                </dd>
              </div>
            </dl>

            <div v-if="exceptionQuantity(card)" class="exception-summary">
              <strong>异常明细</strong>
              <span>返工 {{ card.rework_quantity }}</span>
              <span>报废 {{ card.scrap_quantity }}</span>
              <span>丢失 {{ card.lost_quantity }}</span>
            </div>

            <ElCollapse v-if="card.work_orders.length" class="work-order-collapse">
              <ElCollapseItem :title="`查看工单明细（${card.work_orders.length}）`">
                <ElTable :data="card.work_orders" border table-layout="auto" size="small">
                  <ElTableColumn prop="work_order_no" label="工单号" min-width="150" />
                  <ElTableColumn label="工人/公司" min-width="110">
                    <template #default="{ row }">{{ row.worker_name || '—' }}</template>
                  </ElTableColumn>
                  <ElTableColumn prop="quantity" label="工单数" min-width="80" align="right" />
                  <ElTableColumn prop="processed_quantity" label="加工数" min-width="80" align="right" />
                  <ElTableColumn prop="submitted_quantity" label="送检数" min-width="80" align="right" />
                  <ElTableColumn prop="pending_qc_quantity" label="待检数" min-width="80" align="right" />
                  <ElTableColumn prop="completed_quantity" label="完成数" min-width="80" align="right" />
                  <ElTableColumn prop="rework_quantity" label="返工" min-width="70" align="right" />
                  <ElTableColumn prop="scrap_quantity" label="报废" min-width="70" align="right" />
                  <ElTableColumn prop="lost_quantity" label="丢失" min-width="70" align="right" />
                  <ElTableColumn label="状态" min-width="80">
                    <template #default="{ row }">
                      {{ workOrderStatusLabel(row.status) }}
                    </template>
                  </ElTableColumn>
                  <ElTableColumn prop="created_at" label="创建时间" min-width="150" />
                  <ElTableColumn label="完成时间" min-width="150">
                    <template #default="{ row }">{{ row.closed_at || '—' }}</template>
                  </ElTableColumn>
                </ElTable>
              </ElCollapseItem>
            </ElCollapse>
            <p v-else class="no-work-order">尚未创建工单</p>
          </article>
        </div>
        <ElEmpty v-else description="该生产项暂无可展示的加工标记" />
      </template>
      <ElEmpty v-else-if="!loading" description="生产情况未加载" />
    </div>
  </ElDrawer>
</template>

<style scoped>
:global(.el-overlay.is-drawer.production-progress-overlay) {
  --erp-drawer-transition-duration: 300ms;
  background-color: transparent !important;
}

.drawer-body {
  min-height: 360px;
}

.item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;
  padding: 18px 20px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-low);
}

.item-header h2,
.item-header p,
.card-header h3,
.card-header p {
  margin: 0;
}

.item-header h2 {
  margin: 4px 0;
  font-size: 20px;
}

.item-kicker,
.card-header p,
.no-work-order {
  color: var(--md-on-surface-variant);
}

.item-header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.tag-card-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.tag-progress-card {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}

.tag-progress-card.focused {
  border-color: var(--md-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--md-primary) 18%, transparent);
}

.card-header,
.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header {
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
}

.card-header h3 {
  font-size: 18px;
}

.card-header p {
  margin-top: 5px;
  font-size: 13px;
}

.quantity-progress-track {
  display: flex;
  width: 100%;
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--md-surface-container-high);
}

.quantity-progress-segment {
  flex: 0 0 auto;
  height: 100%;
}

.quantity-progress-segment.completed {
  background: var(--el-color-success);
}

.quantity-progress-segment.exception {
  background: var(--el-color-danger);
}

.quantity-progress-segment.processing {
  background: #f4b400;
}

.quantity-progress-segment.submitted {
  background: #7e57c2;
}

.quantity-progress-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  margin-top: 8px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.quantity-progress-legend span::before {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  content: '';
}

.quantity-progress-legend .completed::before {
  background: var(--el-color-success);
}

.quantity-progress-legend .exception::before {
  background: var(--el-color-danger);
}

.quantity-progress-legend .processing::before {
  background: #f4b400;
}

.quantity-progress-legend .submitted::before {
  background: #7e57c2;
}

.card-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0 0;
}

.card-metrics div {
  padding: 10px;
  border-radius: var(--erp-radius-md);
  background: var(--md-surface-container-low);
}

.card-metrics dt {
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.card-metrics dd {
  margin: 4px 0 0;
  font-size: 17px;
  font-weight: 700;
}

.danger {
  color: var(--erp-danger);
}

.exception-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 18px;
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--el-color-danger) 45%, transparent);
  border-radius: var(--erp-radius-md);
  color: var(--el-color-danger);
  background: color-mix(in srgb, var(--el-color-danger) 8%, transparent);
  font-size: 13px;
}

.work-order-collapse {
  margin-top: 12px;
}

.no-work-order {
  margin: 16px 0 0;
  text-align: center;
  font-size: 13px;
}

@media (max-width: 680px) {
  .item-header,
  .item-header-meta {
    align-items: flex-start;
    flex-direction: column;
  }

  .card-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

</style>
