<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWorkOrdersStore } from '@/stores/workOrders'
import { DEPARTMENT_LABELS } from '@/types/production'
import type {
  InspectionPayload,
  PendingQcBatch,
} from '@/types/production'

const router = useRouter()
const authStore = useAuthStore()
const workOrdersStore = useWorkOrdersStore()
const { loading, pendingQc, workers } = storeToRefs(workOrdersStore)
const inspectionDialogVisible = ref(false)
const assignmentDialogVisible = ref(false)
const workerDialogVisible = ref(false)
const activeBatch = ref<PendingQcBatch | null>(null)
const workerName = ref('')
const assignmentWorkerId = ref(0)
const form = reactive<InspectionPayload>({
  okQuantity: 0,
  reworkQuantity: 0,
  scrapQuantity: 0,
  lostQuantity: 0,
  defectReason: '',
})

const resultTotal = computed(
  () => form.okQuantity + form.reworkQuantity + form.scrapQuantity + form.lostQuantity,
)
const resultMatches = computed(
  () => Boolean(activeBatch.value && resultTotal.value === activeBatch.value.submittedQuantity),
)
const externalPendingQc = computed(() =>
  pendingQc.value.filter((batch) => batch.ownerDepartment !== 'qc'),
)

function openInspection(batch: PendingQcBatch) {
  if (!batch.qcWorkerId) {
    ElMessage.warning('请先分配 QC 工人')
    return
  }
  activeBatch.value = batch
  form.okQuantity = batch.submittedQuantity
  form.reworkQuantity = 0
  form.scrapQuantity = 0
  form.lostQuantity = 0
  form.defectReason = ''
  inspectionDialogVisible.value = true
}

async function submitInspection() {
  if (!activeBatch.value || !resultMatches.value) {
    ElMessage.warning('结果数量之和必须等于送检数量')
    return
  }
  try {
    await workOrdersStore.inspect(activeBatch.value.id, form)
    inspectionDialogVisible.value = false
    ElMessage.success('质检结果已提交，记录不可修改')
  } catch {
    ElMessage.error('质检提交失败，请检查数量')
  }
}

function openAssignment(batch: PendingQcBatch) {
  activeBatch.value = batch
  assignmentWorkerId.value = batch.qcWorkerId ?? workers.value[0]?.id ?? 0
  assignmentDialogVisible.value = true
}

async function submitAssignment() {
  if (!activeBatch.value || !assignmentWorkerId.value) {
    ElMessage.warning('请选择 QC 工人')
    return
  }
  try {
    await workOrdersStore.assignQcWorker(activeBatch.value.id, assignmentWorkerId.value)
    assignmentDialogVisible.value = false
    ElMessage.success('待质检批次已分配')
  } catch {
    ElMessage.error('分配失败，请确认批次和 QC 工人状态')
  }
}

async function submitWorker() {
  if (!workerName.value.trim()) {
    return
  }
  try {
    await workOrdersStore.addWorker('qc', workerName.value)
    workerName.value = ''
    workerDialogVisible.value = false
    ElMessage.success('QC 工人已添加')
  } catch {
    ElMessage.error('添加 QC 工人失败')
  }
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

async function loadDashboard() {
  await workOrdersStore.loadPendingQc()
}

onMounted(loadDashboard)
</script>

<template>
  <main class="dashboard-page">
    <header class="dashboard-header">
      <div class="navbar-title">
        <div class="page-kicker">QC 部门</div>
        <h1>QC 质检台</h1>
      </div>
      <nav class="header-actions" aria-label="QC 导航">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton class="nav-current" type="primary" aria-current="page">QC 质检台</ElButton>
        <ElButton v-permission="'task:assign'" @click="workerDialogVisible = true">
          添加 QC 工人
        </ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </nav>
    </header>

    <section v-loading="loading" class="section-card">
      <div class="block-heading">
        <div>
          <h2>其他部门待质检批次</h2>
          <p>QC 仅处理其他部门工艺产生的送检批次，不接收正式产品库存。</p>
        </div>
        <span>{{ externalPendingQc.length }} 个批次</span>
      </div>
      <div class="submission-list">
        <article
          v-for="batch in externalPendingQc"
          :key="batch.id"
          class="submission-card"
        >
          <div>
            <span>
              {{ batch.workOrderNo }} · {{ DEPARTMENT_LABELS[batch.ownerDepartment] }}工单
            </span>
            <strong>{{ batch.productName }} / {{ batch.processName }}</strong>
            <em>
              订单 {{ batch.orderId }} · {{ batch.zzCode }} · 原工人 {{ batch.workerName }}
            </em>
          </div>
          <div class="submission-actions">
            <strong>送检 {{ batch.submittedQuantity }}</strong>
            <ElTag v-if="batch.qcWorkerName" type="success">
              已分配：{{ batch.qcWorkerName }}
            </ElTag>
            <ElTag v-else type="warning">待分配</ElTag>
            <ElButton
              v-permission="'task:assign'"
              size="small"
              @click="openAssignment(batch)"
            >
              {{ batch.qcWorkerId ? '重新分配' : '分配 QC 工人' }}
            </ElButton>
            <ElButton
              v-if="batch.qcWorkerId"
              v-permission="'task:complete'"
              type="primary"
              size="small"
              @click="openInspection(batch)"
            >
              质检完成，录入结果
            </ElButton>
          </div>
        </article>
        <ElEmpty
          v-if="externalPendingQc.length === 0"
          description="暂无其他部门的待质检批次"
        />
      </div>
    </section>

    <ElDialog v-model="inspectionDialogVisible" title="录入 QC 结果" width="540px">
      <div class="inspection-summary">
        <strong>{{ activeBatch?.productName }} / {{ activeBatch?.processName }}</strong>
        <span>本次送检：{{ activeBatch?.submittedQuantity }}</span>
      </div>
      <ElAlert
        :title="`质检工人：${activeBatch?.qcWorkerName || '-'}`"
        type="info"
        :closable="false"
        show-icon
      />
      <ElForm label-position="top">
        <div class="quantity-grid">
          <ElFormItem label="OK"><ElInputNumber v-model="form.okQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="返修"><ElInputNumber v-model="form.reworkQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="报废"><ElInputNumber v-model="form.scrapQuantity" :min="0" /></ElFormItem>
          <ElFormItem label="遗失"><ElInputNumber v-model="form.lostQuantity" :min="0" /></ElFormItem>
        </div>
        <ElFormItem label="不良原因">
          <ElInput v-model="form.defectReason" type="textarea" />
        </ElFormItem>
      </ElForm>
      <div :class="['total-check', { invalid: !resultMatches }]">
        结果合计 {{ resultTotal }} / 送检 {{ activeBatch?.submittedQuantity }}
      </div>
      <template #footer>
        <ElButton @click="inspectionDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!resultMatches" @click="submitInspection">
          确认并永久提交
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="assignmentDialogVisible" title="分配 QC 工人" width="440px">
      <div class="assignment-summary">
        <strong>{{ activeBatch?.productName }} / {{ activeBatch?.processName }}</strong>
        <span>送检数量：{{ activeBatch?.submittedQuantity }}</span>
      </div>
      <ElForm label-position="top">
        <ElFormItem label="QC 工人" required>
          <ElSelect v-model="assignmentWorkerId" placeholder="请选择 QC 工人">
            <ElOption
              v-for="worker in workers"
              :key="worker.id"
              :label="worker.name"
              :value="worker.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="assignmentDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!assignmentWorkerId" @click="submitAssignment">
          确认分配
        </ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="workerDialogVisible" title="添加 QC 工人" width="420px">
      <ElInput v-model="workerName" placeholder="QC 工人姓名" @keyup.enter="submitWorker" />
      <template #footer>
        <ElButton @click="workerDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :disabled="!workerName.trim()" @click="submitWorker">添加</ElButton>
      </template>
    </ElDialog>

  </main>
</template>

<style scoped>
.dashboard-page {
  min-height: 100vh;
  padding: 22px;
  background: var(--erp-bg);
}

.dashboard-header,
.section-card,
.submission-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 16px 20px;
}

.dashboard-header h1,
.section-card h2 { margin: 6px 0; }
.navbar-title h1 { margin-bottom: 0; font-size: 22px; }
.dashboard-header p { margin: 0; color: var(--erp-text-muted); }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.header-actions,
.submission-actions { display: flex; gap: 10px; align-items: center; }
.header-actions { flex-wrap: wrap; justify-content: flex-end; }
.header-actions :deep(.el-button + .el-button) { margin-left: 0; }
.nav-current { pointer-events: none; }
.section-card { margin-bottom: 18px; padding: 18px; }
.block-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}
.block-heading > div { display: grid; gap: 4px; }
.block-heading h3 { margin: 0; font-size: 16px; }
.block-heading p { margin: 0; color: var(--erp-text-muted); font-size: 13px; }
.block-heading span { color: var(--erp-text-muted); font-size: 13px; }
.submission-list { display: grid; gap: 12px; margin-top: 16px; }
.submission-card { display: flex; justify-content: space-between; gap: 16px; padding: 16px; }
.submission-actions { flex-wrap: wrap; justify-content: flex-end; }
.submission-card > div:first-child { display: grid; gap: 4px; }
.submission-card span,
.submission-card em { color: var(--erp-text-muted); font-size: 13px; font-style: normal; }
.inspection-summary,
.assignment-summary { display: flex; justify-content: space-between; margin-bottom: 16px; }
.inspection-summary + .el-alert { margin-bottom: 16px; }
.quantity-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.total-check { padding: 12px; border-radius: 8px; background: #ecfdf5; color: var(--erp-success); font-weight: 700; }
.total-check.invalid { background: #fef2f2; color: var(--erp-danger); }

@media (max-width: 760px) {
  .dashboard-header,
  .submission-card { flex-direction: column; }
  .dashboard-header { align-items: flex-start; }
  .header-actions { justify-content: flex-start; width: 100%; }
  .submission-actions { justify-content: flex-start; }
  .quantity-grid { grid-template-columns: 1fr; }
}
</style>
