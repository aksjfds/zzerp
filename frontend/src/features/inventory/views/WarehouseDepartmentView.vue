<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import {
  queryWarehouseOperations,
  queryWarehouseStocks,
  reviewWarehouseOperation,
  reverseProductionStorage,
} from '../api/inventory'
import type {
  WarehouseOperation,
  WarehouseOperationStatus,
  WarehouseStock,
} from '../domain/types'

const loading = ref(false)
const reviewingGroupNo = ref<string | null>(null)
const stocks = ref<WarehouseStock[]>([])
const operations = ref<WarehouseOperation[]>([])
const operationStatus = ref<WarehouseOperationStatus | ''>('')

const itemTypeLabels = { part: '普通配件', assembly: '装配体' } as const
const operationTypeLabels = { inbound: '入库', outbound: '出库' } as const
const operationSourceLabels = {
  plan_confirmation: '生产计划确认',
  qc_inventory: 'QC 合格品入库',
  production_position: '生产节点直接入库',
  reversal: '冲销',
} as const
const reversedOperationIds = computed(() => new Set(
  operations.value
    .map(item => item.reversal_of_operation_id)
    .filter((id): id is number => id !== null),
))

function canReverseStorage(operation: WarehouseOperation) {
  return operation.source_type === 'production_position'
    && operation.status === 'succeeded'
    && !reversedOperationIds.value.has(operation.id)
}

async function reverseStorage(operation: WarehouseOperation) {
  try {
    await ElMessageBox.confirm(
      '仅该批库存尚未被领用、且物料没有后续生产流转时可以冲销。库存会扣回并恢复原生产位置。',
      '冲销生产节点物料入库',
      { type: 'warning', confirmButtonText: '确认冲销', cancelButtonText: '取消' },
    )
    await reverseProductionStorage(operation.operation_group_no)
    await load()
    ElMessage.success('生产节点物料入库已冲销')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '生产节点物料入库冲销失败')
    }
  }
}
const operationStatusLabels = {
  pending: '待执行',
  succeeded: '成功',
  failed: '失败',
  uncertain: '结果待核对',
} as const
const operationStatusTypes = {
  pending: 'info',
  succeeded: 'success',
  failed: 'danger',
  uncertain: 'warning',
} as const
async function load() {
  loading.value = true
  try {
    const [nextStocks, nextOperations] = await Promise.all([
      queryWarehouseStocks(),
      queryWarehouseOperations(operationStatus.value || undefined),
    ])
    stocks.value = nextStocks
    operations.value = nextOperations
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '仓库数据加载失败')
  } finally {
    loading.value = false
  }
}

async function review(operation: WarehouseOperation) {
  try {
    const { value } = await ElMessageBox.prompt(
      '请填写对本项目此次仓库操作的人工核对说明。该操作不会修改库存数量或执行状态。',
      '记录人工核对',
      {
        inputType: 'textarea',
        inputPattern: /\S+/,
        inputErrorMessage: '请填写核对说明',
        confirmButtonText: '保存核对说明',
        cancelButtonText: '取消',
      },
    )
    reviewingGroupNo.value = operation.operation_group_no
    await reviewWarehouseOperation(operation.operation_group_no, value.trim())
    ElMessage.success('人工核对说明已保存')
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '人工核对说明保存失败')
    }
  } finally {
    reviewingGroupNo.value = null
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="warehouse-page">
    <DepartmentPageHeader
      department-name="仓库"
      description="查看临时仓库当前库存及本项目发起的仓库操作。"
      @refresh="load"
    />
    <ElTabs>
      <ElTabPane label="当前库存">
        <ElTable
          v-table-column-widths="'warehouse.temporary-stocks'"
          :data="stocks"
          border
          stripe
          table-layout="auto"
          empty-text="暂无临时仓库库存"
        >
          <ElTableColumn prop="item_code" label="品号" min-width="150" />
          <ElTableColumn prop="item_name" label="品名" min-width="180" />
          <ElTableColumn prop="specification" label="规格" min-width="110">
            <template #default="{ row }">{{ row.specification || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="product_version" label="版本" width="80" />
          <ElTableColumn label="物料类型" width="100">
            <template #default="{ row }">{{ itemTypeLabels[row.item_type as keyof typeof itemTypeLabels] }}</template>
          </ElTableColumn>
          <ElTableColumn prop="completion_status" label="加工状态" min-width="130" />
          <ElTableColumn label="仓库" min-width="140">
            <template #default="{ row }">{{ row.warehouse_code }} · {{ row.warehouse_name }}</template>
          </ElTableColumn>
          <ElTableColumn prop="inventory_unit" label="单位" width="80" />
          <ElTableColumn prop="quantity" label="库存数量" width="100" align="right" />
          <ElTableColumn prop="last_inbound_date" label="最近入库日" width="120">
            <template #default="{ row }">{{ row.last_inbound_date || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn prop="last_outbound_date" label="最近出库日" width="120">
            <template #default="{ row }">{{ row.last_outbound_date || '—' }}</template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>
      <ElTabPane label="本项目操作记录">
        <div class="operation-heading">
          <p>这里只记录本项目发起的操作，不代表实际 SQL Server 仓库的全部流水。</p>
          <ElSelect
            v-model="operationStatus"
            clearable
            placeholder="全部执行状态"
            @change="load"
          >
            <ElOption label="待执行" value="pending" />
            <ElOption label="成功" value="succeeded" />
            <ElOption label="失败" value="failed" />
            <ElOption label="结果待核对" value="uncertain" />
          </ElSelect>
        </div>
        <ElTable
          v-table-column-widths="'warehouse.project-operations'"
          :data="operations"
          border
          stripe
          table-layout="auto"
          empty-text="暂无本项目仓库操作"
        >
          <ElTableColumn prop="created_at" label="创建时间" min-width="175" />
          <ElTableColumn prop="operation_no" label="本地操作号" min-width="220" show-overflow-tooltip />
          <ElTableColumn label="操作" width="80">
            <template #default="{ row }">{{ operationTypeLabels[row.operation_type as keyof typeof operationTypeLabels] }}</template>
          </ElTableColumn>
          <ElTableColumn label="业务来源" min-width="150">
            <template #default="{ row }">{{ operationSourceLabels[row.source_type as keyof typeof operationSourceLabels] }}</template>
          </ElTableColumn>
          <ElTableColumn label="物料" min-width="230">
            <template #default="{ row }">
              <div>{{ row.item_code }} · {{ row.item_name }}</div>
              <small>V{{ row.product_version }} · {{ row.completion_status }}</small>
            </template>
          </ElTableColumn>
          <ElTableColumn label="仓库" min-width="130">
            <template #default="{ row }">{{ row.warehouse_code }} · {{ row.warehouse_name }}</template>
          </ElTableColumn>
          <ElTableColumn prop="quantity" label="数量" width="90" align="right" />
          <ElTableColumn label="变动前 / 后" width="120" align="right">
            <template #default="{ row }">
              {{ row.quantity_before ?? '—' }} / {{ row.quantity_after ?? '—' }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="执行状态" min-width="120">
            <template #default="{ row }">
              <ElTag :type="operationStatusTypes[row.status as keyof typeof operationStatusTypes]" effect="light">
                {{ operationStatusLabels[row.status as keyof typeof operationStatusLabels] }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
          <ElTableColumn label="异常与核对" min-width="230">
            <template #default="{ row }">
              <div v-if="row.error_message">{{ row.error_message }}</div>
              <small v-if="row.manual_reviewed_at">
                {{ row.manual_reviewed_by }}：{{ row.manual_review_note }}
              </small>
              <span v-if="!row.error_message && !row.manual_reviewed_at">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <ElButton
                v-if="row.can_review"
                v-permission="PRODUCTION_PERMISSIONS.manage"
                link
                type="primary"
                :loading="reviewingGroupNo === row.operation_group_no"
                :disabled="reviewingGroupNo !== null && reviewingGroupNo !== row.operation_group_no"
                @click="review(row)"
              >记录核对</ElButton>
              <ElButton
                v-else-if="canReverseStorage(row)"
                v-permission="PRODUCTION_PERMISSIONS.manage"
                link
                type="danger"
                @click="reverseStorage(row)"
              >冲销</ElButton>
              <span v-else>—</span>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>
    </ElTabs>
  </section>
</template>

<style scoped>
.warehouse-page { padding: 24px; }
.operation-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.operation-heading p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.operation-heading :deep(.el-select) { width: 180px; }
.warehouse-page small { display: block; color: var(--el-text-color-secondary); }
@media (max-width: 640px) {
  .operation-heading { align-items: stretch; flex-direction: column; }
  .operation-heading :deep(.el-select) { width: 100%; }
}
</style>
