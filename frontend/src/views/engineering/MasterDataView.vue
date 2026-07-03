<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  createV2SurfaceTreatment,
  createV2Workshop,
  queryV2Departments,
  queryV2SurfaceTreatments,
  queryV2Workshops,
  updateV2SurfaceTreatment,
  updateV2Workshop,
} from '@/api/engineering'
import type {
  DepartmentSummary,
  SurfaceTreatmentSummary,
  WorkshopSummary,
} from '@/types/engineering'

const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()
const departments = ref<DepartmentSummary[]>([])
const workshops = ref<WorkshopSummary[]>([])
const treatments = ref<SurfaceTreatmentSummary[]>([])
const workshopDialogVisible = ref(false)
const treatmentDialogVisible = ref(false)
const workshopForm = reactive({ departmentId: 0, workshopCode: '', workshopName: '' })
const treatmentForm = reactive({ customerName: '', treatmentName: '' })

const productionDepartments = computed(() =>
  departments.value.filter((item) => item.departmentType === 'production' && item.active),
)
const departmentMap = computed(
  () => new Map(departments.value.map((item) => [item.id, item.departmentName])),
)

async function loadData() {
  loading.value = true
  try {
    const [departmentData, workshopData, treatmentData] = await Promise.all([
      queryV2Departments(),
      queryV2Workshops(),
      queryV2SurfaceTreatments(),
    ])
    departments.value = departmentData
    workshops.value = workshopData
    treatments.value = treatmentData
  } catch {
    ElMessage.error('基础资料加载失败')
  } finally {
    loading.value = false
  }
}

function openWorkshopDialog() {
  workshopForm.departmentId = productionDepartments.value[0]?.id ?? 0
  workshopForm.workshopCode = ''
  workshopForm.workshopName = ''
  workshopDialogVisible.value = true
}

async function submitWorkshop() {
  try {
    await createV2Workshop(workshopForm)
    workshopDialogVisible.value = false
    await loadData()
    ElMessage.success('车间已添加')
  } catch {
    ElMessage.error('车间添加失败，请检查编码和名称')
  }
}

async function toggleWorkshop(item: WorkshopSummary) {
  try {
    await updateV2Workshop(item.id, { active: !item.active })
    await loadData()
  } catch {
    ElMessage.error('车间状态更新失败')
  }
}

function openTreatmentDialog() {
  treatmentForm.customerName = ''
  treatmentForm.treatmentName = ''
  treatmentDialogVisible.value = true
}

async function submitTreatment() {
  try {
    await createV2SurfaceTreatment(
      treatmentForm.customerName,
      treatmentForm.treatmentName,
    )
    treatmentDialogVisible.value = false
    await loadData()
    ElMessage.success('客户表面处理已添加')
  } catch {
    ElMessage.error('表面处理添加失败')
  }
}

async function toggleTreatment(item: SurfaceTreatmentSummary) {
  try {
    await updateV2SurfaceTreatment(item.id, { active: !item.active })
    await loadData()
  } catch {
    ElMessage.error('表面处理状态更新失败')
  }
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(loadData)
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div>
        <span>基础资料</span>
        <h1>车间与客户表面处理</h1>
      </div>
      <div class="header-actions">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton @click="router.push('/dashboard/engineering')">产品资料</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </div>
    </header>

    <div v-loading="loading" class="content-grid">
      <section class="content-card">
        <div class="section-head">
          <div><h2>生产车间</h2><p>车间停用后保留历史引用。</p></div>
          <ElButton type="primary" @click="openWorkshopDialog">新增车间</ElButton>
        </div>
        <ElTable :data="workshops" stripe>
          <ElTableColumn label="部门">
            <template #default="{ row }">{{ departmentMap.get(row.departmentId) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="workshopCode" label="车间编码" />
          <ElTableColumn prop="workshopName" label="车间名称" />
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">{{ row.active ? '启用' : '停用' }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="100">
            <template #default="{ row }">
              <ElButton text @click="toggleWorkshop(row)">
                {{ row.active ? '停用' : '启用' }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div><h2>客户表面处理</h2><p>相同名称在不同客户下独立维护。</p></div>
          <ElButton type="primary" @click="openTreatmentDialog">新增处理</ElButton>
        </div>
        <ElTable :data="treatments" stripe>
          <ElTableColumn prop="customerName" label="客户" />
          <ElTableColumn prop="treatmentName" label="表面处理" />
          <ElTableColumn label="状态" width="90">
            <template #default="{ row }">{{ row.active ? '启用' : '停用' }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="100">
            <template #default="{ row }">
              <ElButton text @click="toggleTreatment(row)">
                {{ row.active ? '停用' : '启用' }}
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </section>
    </div>

    <ElDialog v-model="workshopDialogVisible" title="新增车间" width="500px">
      <ElForm label-position="top">
        <ElFormItem label="部门">
          <ElSelect v-model="workshopForm.departmentId">
            <ElOption
              v-for="item in productionDepartments"
              :key="item.id"
              :label="item.departmentName"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="车间编码">
          <ElInput v-model="workshopForm.workshopCode" />
        </ElFormItem>
        <ElFormItem label="车间名称">
          <ElInput v-model="workshopForm.workshopName" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="workshopDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitWorkshop">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog v-model="treatmentDialogVisible" title="新增客户表面处理" width="500px">
      <ElForm label-position="top">
        <ElFormItem label="客户名称">
          <ElInput v-model="treatmentForm.customerName" />
        </ElFormItem>
        <ElFormItem label="表面处理">
          <ElInput v-model="treatmentForm.treatmentName" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="treatmentDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitTreatment">保存</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 22px; background: var(--erp-bg); }
.page-header,
.content-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
  padding: 16px 20px;
}
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 6px 0 0; }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.content-card { padding: 18px; }
.section-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.section-head h2 { margin: 0; }
.section-head p { margin: 6px 0 0; color: var(--erp-text-muted); }
@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
  .section-head { align-items: flex-start; flex-direction: column; }
}
</style>
