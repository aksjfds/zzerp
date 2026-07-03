<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  createV2BomVersion,
  createV2MaterialRoute,
  createV2SemiFinishedVersion,
  deleteV2BomVersion,
  deleteV2MaterialRoute,
  deleteV2SemiFinishedVersion,
  publishV2BomVersion,
  publishV2MaterialRoute,
  publishV2SemiFinishedVersion,
  queryV2BomVersions,
  queryV2Departments,
  queryV2MaterialRoutes,
  queryV2Product,
  queryV2ProductionStructure,
  queryV2SemiFinishedVersions,
  queryV2Workshops,
  updateV2BomVersion,
  updateV2MaterialRoute,
  updateV2SemiFinishedVersion,
} from '@/api/engineering'
import type {
  DepartmentSummary,
  EngineeringProduct,
  MaterialRouteVersion,
  ProductBomVersion,
  ProductionStructure,
  SemiFinishedVersion,
  WorkshopSummary,
} from '@/types/engineering'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const productId = Number(route.params.productId)
const loading = ref(false)
const product = ref<EngineeringProduct>()
const bomVersions = ref<ProductBomVersion[]>([])
const semiVersions = ref<SemiFinishedVersion[]>([])
const routeVersions = ref<MaterialRouteVersion[]>([])
const departments = ref<DepartmentSummary[]>([])
const workshops = ref<WorkshopSummary[]>([])
const structure = ref<ProductionStructure>()
const structureMessage = ref('请先发布产品BOM')
const bomDialogVisible = ref(false)
const semiDialogVisible = ref(false)
const routeDialogVisible = ref(false)
const editingBomId = ref<number>()
const editingSemiId = ref<number>()
const editingRouteId = ref<number>()
const semiMaterialId = ref<number>()
const bomForm = reactive({ items: [] as Array<{ materialId?: number; quantity: number }> })
const semiForm = reactive({
  quantityPerFinished: 1,
  inputs: [] as Array<{ inputMaterialId?: number; quantity: number }>,
})
const routeForm = reactive({
  materialId: undefined as number | undefined,
  steps: [] as Array<{
    stepType: 'internal' | 'external_surface'
    departmentId?: number
    workshopId?: number
  }>,
})

const partOptions = computed(() => product.value?.materials.filter(
  (item) => item.active && ['self_made', 'purchased'].includes(item.materialType),
) ?? [])
const semiOptions = computed(() => product.value?.materials.filter(
  (item) => item.active && item.materialType === 'semi_finished',
) ?? [])
const semiInputOptions = computed(() => product.value?.materials.filter(
  (item) => item.active
    && item.materialType !== 'finished'
    && item.id !== semiMaterialId.value,
) ?? [])
const routeMaterialOptions = computed(() => product.value?.materials.filter(
  (item) => item.active && item.materialType !== 'purchased',
) ?? [])
const productionDepartments = computed(() => departments.value.filter(
  (item) => item.active && item.departmentType === 'production',
))

function statusLabel(status: string) {
  return { draft: '草稿', published: '已发布', inactive: '已停用' }[status] ?? status
}

function bomSummary(version: ProductBomVersion) {
  return version.items
    .map((item) => `${item.materialName} × ${item.quantity}`)
    .join('；')
}

function semiSummary(version: SemiFinishedVersion) {
  return version.inputs
    .map((item) => `${item.materialCode} ${item.materialName} × ${item.quantity}`)
    .join('；')
}

function routeSummary(version: MaterialRouteVersion) {
  return version.steps.map((item) => (
    item.stepType === 'external_surface'
      ? '外厂表面处理'
      : `${item.departmentName} / ${item.workshopName}`
  )).join(' → ')
}

function workshopOptions(departmentId?: number) {
  return workshops.value.filter(
    (item) => item.active && item.departmentId === departmentId,
  )
}

function addRouteStep() {
  const lastIndex = routeForm.steps.length - 1
  if (routeForm.steps[lastIndex]?.stepType === 'external_surface') {
    routeForm.steps.splice(lastIndex, 0, { stepType: 'internal' })
    return
  }
  routeForm.steps.push({ stepType: 'internal' })
}

function moveRouteStep(index: number, offset: number) {
  const target = index + offset
  if (target < 0 || target >= routeForm.steps.length) return
  const [step] = routeForm.steps.splice(index, 1)
  routeForm.steps.splice(target, 0, step)
}

function changeStepType(index: number) {
  routeForm.steps[index].departmentId = undefined
  routeForm.steps[index].workshopId = undefined
}

function changeStepDepartment(index: number) {
  routeForm.steps[index].workshopId = undefined
}

function addBomItem() {
  bomForm.items.push({ materialId: undefined, quantity: 1 })
}

function addSemiInput() {
  semiForm.inputs.push({ inputMaterialId: undefined, quantity: 1 })
}

async function loadData() {
  loading.value = true
  try {
    ;[
      product.value,
      bomVersions.value,
      semiVersions.value,
      routeVersions.value,
      departments.value,
      workshops.value,
    ] = await Promise.all([
      queryV2Product(productId),
      queryV2BomVersions(productId),
      queryV2SemiFinishedVersions(productId),
      queryV2MaterialRoutes(productId),
      queryV2Departments(),
      queryV2Workshops(),
    ])
    try {
      structure.value = await queryV2ProductionStructure(productId)
    } catch {
      structure.value = undefined
      structureMessage.value = (
        '发布BOM后显示生产结构；已配置的半成品组成会自动展开'
      )
    }
  } catch {
    ElMessage.error('产品生产结构加载失败')
  } finally {
    loading.value = false
  }
}

function openBomDialog(version?: ProductBomVersion) {
  editingBomId.value = version?.id
  bomForm.items = version?.items.map((item) => ({
    materialId: item.materialId,
    quantity: item.quantity,
  })) ?? [{ materialId: undefined, quantity: 1 }]
  bomDialogVisible.value = true
}

async function saveBom() {
  if (bomForm.items.some((item) => !item.materialId || item.quantity < 1)) {
    ElMessage.warning('请完整填写BOM配件和用量')
    return
  }
  const payload = {
    items: bomForm.items.map((item) => ({
      materialId: item.materialId as number,
      quantity: item.quantity,
    })),
  }
  try {
    if (editingBomId.value) await updateV2BomVersion(editingBomId.value, payload)
    else await createV2BomVersion(productId, payload)
    bomDialogVisible.value = false
    await loadData()
    ElMessage.success('BOM草稿已保存')
  } catch {
    ElMessage.error('BOM保存失败，请检查配件是否重复')
  }
}

function openSemiDialog(version?: SemiFinishedVersion) {
  editingSemiId.value = version?.id
  semiMaterialId.value = version?.semiFinishedMaterialId
  semiForm.quantityPerFinished = version?.quantityPerFinished ?? 1
  semiForm.inputs = version?.inputs.map((item) => ({
    inputMaterialId: item.inputMaterialId,
    quantity: item.quantity,
  })) ?? [{ inputMaterialId: undefined, quantity: 1 }]
  semiDialogVisible.value = true
}

async function saveSemi() {
  if (!semiMaterialId.value || semiForm.inputs.some(
    (item) => !item.inputMaterialId || item.quantity < 1,
  )) {
    ElMessage.warning('请完整填写半成品及其输入物料')
    return
  }
  const payload = {
    quantityPerFinished: semiForm.quantityPerFinished,
    inputs: semiForm.inputs.map((item) => ({
      inputMaterialId: item.inputMaterialId as number,
      quantity: item.quantity,
    })),
  }
  try {
    if (editingSemiId.value) {
      await updateV2SemiFinishedVersion(editingSemiId.value, payload)
    } else {
      await createV2SemiFinishedVersion(semiMaterialId.value, payload)
    }
    semiDialogVisible.value = false
    await loadData()
    ElMessage.success('半成品组成草稿已保存')
  } catch {
    ElMessage.error('组成保存失败，请检查重复物料或循环引用')
  }
}

function openRouteDialog(version?: MaterialRouteVersion) {
  editingRouteId.value = version?.id
  routeForm.materialId = version?.materialId
  routeForm.steps = version?.steps.map((item) => ({
    stepType: item.stepType,
    departmentId: item.departmentId ?? undefined,
    workshopId: item.workshopId ?? undefined,
  })) ?? [{ stepType: 'internal' }]
  routeDialogVisible.value = true
}

async function saveRoute() {
  const externalIndexes = routeForm.steps.flatMap((item, index) => (
    item.stepType === 'external_surface' ? [index] : []
  ))
  if (
    externalIndexes.length > 1
    || (externalIndexes.length === 1
      && externalIndexes[0] !== routeForm.steps.length - 1)
  ) {
    ElMessage.warning('外厂表面处理最多一个，并且必须是路线最后一步')
    return
  }
  if (!routeForm.materialId || !routeForm.steps.length || routeForm.steps.some((item) => (
    item.stepType === 'internal' && (!item.departmentId || !item.workshopId)
  ))) {
    ElMessage.warning('请完整填写路线物料、部门和车间')
    return
  }
  const payload = {
    steps: routeForm.steps.map((item) => ({
      stepType: item.stepType,
      departmentId: item.stepType === 'internal' ? item.departmentId : undefined,
      workshopId: item.stepType === 'internal' ? item.workshopId : undefined,
    })),
  }
  try {
    if (editingRouteId.value) {
      await updateV2MaterialRoute(editingRouteId.value, payload)
    } else {
      await createV2MaterialRoute(routeForm.materialId, payload)
    }
    routeDialogVisible.value = false
    await loadData()
    ElMessage.success('工艺路线草稿已保存')
  } catch {
    ElMessage.error('工艺路线保存失败')
  }
}

async function publish(kind: 'bom' | 'semi' | 'route', id: number) {
  try {
    await ElMessageBox.confirm('发布后该版本不可修改，确定发布？', '发布版本')
    if (kind === 'bom') await publishV2BomVersion(id)
    else if (kind === 'semi') await publishV2SemiFinishedVersion(id)
    else await publishV2MaterialRoute(id)
    await loadData()
    ElMessage.success('版本已发布')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('版本发布失败')
  }
}

async function removeDraft(kind: 'bom' | 'semi' | 'route', id: number) {
  try {
    await ElMessageBox.confirm('确定删除该草稿？', '删除草稿', { type: 'warning' })
    if (kind === 'bom') await deleteV2BomVersion(id)
    else if (kind === 'semi') await deleteV2SemiFinishedVersion(id)
    else await deleteV2MaterialRoute(id)
    await loadData()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('草稿删除失败')
  }
}

onMounted(loadData)

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}
</script>

<template>
  <main v-loading="loading" class="page-shell">
    <header class="page-header">
      <div>
        <span>工程部 / 产品资料</span>
        <h1>{{ product?.factoryCode }} · {{ product?.productName }}</h1>
      </div>
      <div class="header-actions">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton @click="router.push('/dashboard/engineering')">返回产品列表</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </div>
    </header>

    <ElTabs class="content-card">
      <ElTabPane label="产品 BOM">
        <div class="toolbar">
          <ElButton type="primary" @click="openBomDialog()">新建BOM版本</ElButton>
        </div>
        <ElTable :data="bomVersions" stripe>
          <ElTableColumn prop="versionNo" label="版本" width="90" />
          <ElTableColumn label="状态" width="110">
            <template #default="{ row }"><ElTag>{{ statusLabel(row.status) }}</ElTag></template>
          </ElTableColumn>
          <ElTableColumn label="配件组成" min-width="420">
            <template #default="{ row }">
              {{ bomSummary(row) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status === 'draft'">
                <ElButton text @click="openBomDialog(row)">编辑</ElButton>
                <ElButton text type="primary" @click="publish('bom', row.id)">发布</ElButton>
                <ElButton text type="danger" @click="removeDraft('bom', row.id)">删除</ElButton>
              </template>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="半成品组成">
        <div class="toolbar">
          <ElButton type="primary" @click="openSemiDialog()">新建半成品版本</ElButton>
        </div>
        <ElTable :data="semiVersions" stripe>
          <ElTableColumn prop="materialCode" label="半成品编号" width="150" />
          <ElTableColumn prop="materialName" label="半成品" width="150" />
          <ElTableColumn prop="versionNo" label="版本" width="80" />
          <ElTableColumn prop="quantityPerFinished" label="每成品用量" width="110" />
          <ElTableColumn label="输入物料" min-width="360">
            <template #default="{ row }">
              {{ semiSummary(row) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100">
            <template #default="{ row }">{{ statusLabel(row.status) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status === 'draft'">
                <ElButton text @click="openSemiDialog(row)">编辑</ElButton>
                <ElButton text type="primary" @click="publish('semi', row.id)">发布</ElButton>
                <ElButton text type="danger" @click="removeDraft('semi', row.id)">删除</ElButton>
              </template>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="物料工艺路线">
        <div class="toolbar">
          <ElButton type="primary" @click="openRouteDialog()">新建路线版本</ElButton>
        </div>
        <ElAlert
          title="路线配置部门和车间；具体工序、清洗和QC由车间管理。"
          type="info"
          :closable="false"
          show-icon
        />
        <ElTable :data="routeVersions" stripe class="route-table">
          <ElTableColumn prop="materialCode" label="物料编号" width="150" />
          <ElTableColumn prop="materialName" label="物料名称" width="160" />
          <ElTableColumn prop="versionNo" label="版本" width="80" />
          <ElTableColumn label="路线" min-width="420">
            <template #default="{ row }">{{ routeSummary(row) }}</template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100">
            <template #default="{ row }">{{ statusLabel(row.status) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="200">
            <template #default="{ row }">
              <template v-if="row.status === 'draft'">
                <ElButton text @click="openRouteDialog(row)">编辑</ElButton>
                <ElButton text type="primary" @click="publish('route', row.id)">
                  发布
                </ElButton>
                <ElButton text type="danger" @click="removeDraft('route', row.id)">
                  删除
                </ElButton>
              </template>
            </template>
          </ElTableColumn>
        </ElTable>
      </ElTabPane>

      <ElTabPane label="生产结构">
        <ElTree
          v-if="structure"
          :data="[structure.root]"
          node-key="id"
          default-expand-all
        >
          <template #default="{ data }">
            <span>
              {{ data.materialCode }} · {{ data.materialName }} ×
              {{ data.quantity }} pcs
            </span>
          </template>
        </ElTree>
        <ElEmpty v-else :description="structureMessage" />
      </ElTabPane>
    </ElTabs>

    <ElDialog
      v-model="bomDialogVisible"
      :title="editingBomId ? '编辑BOM草稿' : '新建BOM版本'"
      width="720px"
    >
      <div v-for="(item, index) in bomForm.items" :key="index" class="form-row">
        <ElSelect v-model="item.materialId" filterable placeholder="选择配件">
          <ElOption
            v-for="part in partOptions"
            :key="part.id"
            :label="`${part.materialCode} · ${part.materialName}`"
            :value="part.id"
          />
        </ElSelect>
        <ElInputNumber v-model="item.quantity" :min="1" />
        <ElButton type="danger" text @click="bomForm.items.splice(index, 1)">删除</ElButton>
      </div>
      <ElButton @click="addBomItem">添加配件</ElButton>
      <template #footer>
        <ElButton @click="bomDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="saveBom">保存草稿</ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="semiDialogVisible"
      :title="editingSemiId ? '编辑半成品组成' : '新建半成品组成'"
      width="720px"
    >
      <ElForm label-position="top">
        <ElFormItem label="半成品">
          <ElSelect v-model="semiMaterialId" :disabled="Boolean(editingSemiId)" filterable>
            <ElOption
              v-for="item in semiOptions"
              :key="item.id"
              :label="`${item.materialCode} · ${item.materialName}`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="每件成品需要该半成品数量">
          <ElInputNumber v-model="semiForm.quantityPerFinished" :min="1" />
        </ElFormItem>
      </ElForm>
      <div v-for="(item, index) in semiForm.inputs" :key="index" class="form-row">
        <ElSelect v-model="item.inputMaterialId" filterable placeholder="选择输入物料">
          <ElOption
            v-for="input in semiInputOptions"
            :key="input.id"
            :label="`${input.materialCode} · ${input.materialName}`"
            :value="input.id"
          />
        </ElSelect>
        <ElInputNumber v-model="item.quantity" :min="1" />
        <ElButton type="danger" text @click="semiForm.inputs.splice(index, 1)">删除</ElButton>
      </div>
      <ElButton @click="addSemiInput">添加输入物料</ElButton>
      <template #footer>
        <ElButton @click="semiDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="saveSemi">保存草稿</ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="routeDialogVisible"
      :title="editingRouteId ? '编辑路线草稿' : '新建路线版本'"
      width="860px"
    >
      <ElForm label-position="top">
        <ElFormItem label="路线物料">
          <ElSelect
            v-model="routeForm.materialId"
            :disabled="Boolean(editingRouteId)"
            filterable
            placeholder="选择成品、半成品或自制配件"
          >
            <ElOption
              v-for="item in routeMaterialOptions"
              :key="item.id"
              :label="`${item.materialCode} · ${item.materialName}`"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <div v-for="(step, index) in routeForm.steps" :key="index" class="route-row">
        <span class="sequence">{{ index + 1 }}</span>
        <ElSelect v-model="step.stepType" @change="changeStepType(index)">
          <ElOption label="内部生产" value="internal" />
          <ElOption label="外厂表面处理" value="external_surface" />
        </ElSelect>
        <template v-if="step.stepType === 'internal'">
          <ElSelect
            v-model="step.departmentId"
            placeholder="选择部门"
            @change="changeStepDepartment(index)"
          >
            <ElOption
              v-for="item in productionDepartments"
              :key="item.id"
              :label="item.departmentName"
              :value="item.id"
            />
          </ElSelect>
          <ElSelect v-model="step.workshopId" placeholder="选择车间">
            <ElOption
              v-for="item in workshopOptions(step.departmentId)"
              :key="item.id"
              :label="item.workshopName"
              :value="item.id"
            />
          </ElSelect>
        </template>
        <span v-else class="external-tip">具体表面处理随客户订单确定</span>
        <div class="step-actions">
          <ElButton text :disabled="index === 0" @click="moveRouteStep(index, -1)">上移</ElButton>
          <ElButton
            text
            :disabled="index === routeForm.steps.length - 1"
            @click="moveRouteStep(index, 1)"
          >
            下移
          </ElButton>
          <ElButton type="danger" text @click="routeForm.steps.splice(index, 1)">
            删除
          </ElButton>
        </div>
      </div>
      <ElButton @click="addRouteStep">添加步骤</ElButton>
      <template #footer>
        <ElButton @click="routeDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="saveRoute">保存草稿</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 22px; background: var(--erp-bg); }
.page-header, .content-card {
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
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 6px 0 0; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.content-card { padding: 18px; }
.toolbar { display: flex; justify-content: flex-end; margin-bottom: 14px; }
.route-table { margin-top: 14px; }
.form-row { display: grid; grid-template-columns: 1fr 160px auto; gap: 10px; margin-bottom: 10px; }
.route-row {
  display: grid;
  grid-template-columns: 34px 150px 1fr 1fr 190px;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.sequence { color: var(--erp-primary); font-weight: 700; text-align: center; }
.external-tip { grid-column: span 2; color: var(--el-text-color-secondary); }
.step-actions { display: flex; justify-content: flex-end; }
:deep(.el-tree-node__content) { height: 38px; }
</style>
