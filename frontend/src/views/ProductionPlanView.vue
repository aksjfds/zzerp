<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import CreateWorkOrderDialog from '@/components/workorders/CreateWorkOrderDialog.vue'
import WorkOrderCard from '@/components/workorders/WorkOrderCard.vue'
import { useWorkOrdersStore } from '@/stores/workorders'
import {
  PROCEDURE_LABELS,
  PROCEDURE_OPTIONS,
  type CreateWorkOrderPayload,
  type Procedure,
  type WorkOrderStatus,
} from '@/types/workorder'

const router = useRouter()
const workOrdersStore = useWorkOrdersStore()
const { activeQuantity, loading, totalQuantity, workOrders } = storeToRefs(workOrdersStore)

const dialogVisible = ref(false)
const availableProcedures = [...PROCEDURE_OPTIONS]
const queryForm = workOrdersStore.queryForm
const statusOptions: WorkOrderStatus[] = ['待开工', '加工中', '已完成']

function resetQuery() {
  workOrdersStore.resetQuery()
}

function openCreateDialog() {
  dialogVisible.value = true
}

async function createWorkOrder(payload: CreateWorkOrderPayload) {
  await workOrdersStore.createWorkOrder(payload)
  dialogVisible.value = false
}

function getProcedureLabel(procedure: Procedure) {
  return PROCEDURE_LABELS[procedure]
}

onMounted(() => {
  workOrdersStore.loadWorkOrders()
})
</script>

<template>
  <main class="production-page">
    <header class="production-header">
      <div>
        <ElButton text class="back-button" @click="router.push('/')">返回导航</ElButton>
        <div class="page-kicker">Production Planning</div>
        <h1>生产计划</h1>
        <p>围绕工单组织部件、数量和工序流转，按入库与出库数量查看每道工序的推进情况。</p>
      </div>
      <div class="header-actions">
        <ElButton>导出排程</ElButton>
        <ElButton type="primary" @click="openCreateDialog">添加工单</ElButton>
      </div>
    </header>

    <section class="query-panel">
      <ElForm :model="queryForm" class="query-form" label-position="top">
        <ElFormItem label="工单编号">
          <ElInput v-model="queryForm.orderId" clearable placeholder="例如：MO-20260616" />
        </ElFormItem>
        <ElFormItem label="部件">
          <ElInput v-model="queryForm.item" clearable placeholder="例如：MOG3V45-过桥" />
        </ElFormItem>
        <ElFormItem label="状态">
          <ElSelect v-model="queryForm.status" clearable placeholder="全部状态">
            <ElOption v-for="status in statusOptions" :key="status" :label="status" :value="status" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="包含工序">
          <ElSelect v-model="queryForm.procedure" clearable placeholder="全部工序">
            <ElOption v-for="procedure in availableProcedures" :key="procedure" :label="getProcedureLabel(procedure)"
              :value="procedure" />
          </ElSelect>
        </ElFormItem>
        <div class="query-actions">
          <ElButton @click="resetQuery">重置</ElButton>
          <ElButton type="primary" :loading="loading" @click="workOrdersStore.loadWorkOrders">查询工单</ElButton>
        </div>
      </ElForm>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <span>工单数量</span>
        <strong>{{ workOrders.length }}</strong>
        <small>今日计划</small>
      </div>
      <div class="summary-card">
        <span>计划数量</span>
        <strong>{{ totalQuantity }}</strong>
        <small>全部部件</small>
      </div>
      <div class="summary-card">
        <span>在制数量</span>
        <strong>{{ activeQuantity }}</strong>
        <small>未完成流转</small>
      </div>
      <div class="summary-card">
        <span>标准工序</span>
        <strong>{{ availableProcedures.length }}</strong>
        <small>激光 / 冲压 / CNC / 打磨 / QC</small>
      </div>
    </section>

    <section v-loading="loading" class="order-list">
      <WorkOrderCard
        v-for="order in workOrders"
        :key="order.id"
        :order="order"
        @changed="workOrdersStore.loadWorkOrders"
      />
      <ElEmpty v-if="!loading && workOrders.length === 0" description="暂无匹配工单" />
    </section>

    <CreateWorkOrderDialog v-model="dialogVisible" @submit="createWorkOrder" />
  </main>
</template>

<style scoped>
.production-page {
  min-height: 100vh;
  padding: 22px;
  background:
    linear-gradient(180deg, #f8fafc 0, #edf1f5 320px),
    #edf1f5;
}

.production-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 26px 30px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgb(37 99 235 / 94%), rgb(8 145 178 / 88%)),
    #2563eb;
  color: #ffffff;
  box-shadow: var(--erp-shadow-md);
}

.back-button {
  margin: 0 0 12px -12px;
  color: #dbeafe;
}

.page-kicker {
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.production-header h1 {
  margin: 8px 0 10px;
  font-size: 32px;
  line-height: 1.2;
}

.production-header p {
  max-width: 720px;
  margin: 0;
  color: #e5f2ff;
  font-size: 14px;
  line-height: 1.7;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.header-actions :deep(.el-button:not(.el-button--primary)) {
  border-color: rgb(255 255 255 / 68%);
  background: rgb(255 255 255 / 14%);
  color: #ffffff;
}

.query-panel {
  margin-bottom: 18px;
  padding: 18px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.query-form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 12px;
  align-items: end;
}

.query-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.query-actions {
  display: flex;
  gap: 8px;
  padding-bottom: 1px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.summary-card {
  padding: 18px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: var(--erp-shadow-sm);
}

.summary-card span,
.summary-card small {
  display: block;
  color: var(--erp-text-muted);
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin: 8px 0 6px;
  color: var(--erp-text);
  font-size: 28px;
}

.order-list {
  display: grid;
  gap: 18px;
}

@media (max-width: 1180px) {
  .query-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .query-actions {
    grid-column: 1 / -1;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .production-header {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 760px) {
  .production-page {
    padding: 14px;
  }

  .production-header {
    padding: 22px;
  }

  .production-header h1 {
    font-size: 26px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .query-form {
    grid-template-columns: 1fr;
  }

}
</style>
