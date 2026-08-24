<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import {
  queryProcedurePrices,
  saveProcedurePrices,
} from '../api/procedurePrices'
import type { ProcedurePriceScope } from '../domain/procedurePrices'

const props = withDefaults(defineProps<{ embedded?: boolean; departmentCode?: string }>(), {
  embedded: false,
  departmentCode: '',
})
const emit = defineEmits<{ saved: [] }>()
type DraftProcedure = {
  procedure_id: number | null
  procedure_name: string
  unit_price: number | null
  referenced: boolean
}
const route = useRoute()
const authStore = useAuthStore()
const departmentCode = computed(() => String(
  props.departmentCode || route.params.departmentCode || route.meta.departmentCode || '',
))
const departmentName = computed(() => authStore.department || departmentCode.value || '生产部门')
const canManage = computed(() => authStore.hasPermission(PRODUCTION_PERMISSIONS.manage))
const items = ref<ProcedurePriceScope[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const dialogVisible = ref(false)
const activeScope = ref<ProcedurePriceScope>()
const draft = ref<DraftProcedure[]>([])
const saving = ref(false)

function title(scope: ProcedurePriceScope) {
  return `${scope.factory_code}-${scope.product_name}-${scope.part_name}`
}
function procedureNames(scope: ProcedurePriceScope) {
  return scope.procedures.map(item => item.procedure_name).join('、') || '暂未配置'
}
function open(scope: ProcedurePriceScope) {
  activeScope.value = scope
  draft.value = scope.procedures.map(item => ({
    ...item,
    unit_price: item.unit_price === null ? null : Number(item.unit_price),
  }))
  dialogVisible.value = true
}
function addProcedure() {
  draft.value.push({ procedure_id: null, procedure_name: '', unit_price: null, referenced: false })
}
function removeProcedure(index: number) {
  if (!draft.value[index]?.referenced) draft.value.splice(index, 1)
}
async function load() {
  loading.value = true
  try {
    const result = await queryProcedurePrices(
      departmentCode.value, page.value, pageSize, keyword.value,
    )
    items.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '工艺与单价配置加载失败')
  } finally {
    loading.value = false
  }
}
async function search() {
  page.value = 1
  await load()
}
async function save() {
  const scope = activeScope.value
  if (!scope) return
  const names = draft.value.map(item => item.procedure_name.trim())
  if (names.some(name => !name)) {
    ElMessage.warning('请填写工艺名称')
    return
  }
  if (new Set(names).size !== names.length) {
    ElMessage.warning('同一车间不能重复配置同名工艺')
    return
  }
  saving.value = true
  try {
    await saveProcedurePrices(departmentCode.value, scope, draft.value.map((item, index) => ({
      procedure_id: item.procedure_id,
      procedure_name: names[index]!,
      unit_price: item.unit_price,
    })))
    dialogVisible.value = false
    ElMessage.success('工艺与单价已保存')
    await load()
    emit('saved')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'procedure-price-page': !embedded }">
    <DepartmentPageHeader v-if="!embedded" :department-name="departmentName" page-title="工艺与单价配置" description="按产品、版本、物料和车间维护可选工艺及计件单价。" @refresh="load" />
    <section class="filter-bar">
      <ElInput v-model="keyword" clearable placeholder="搜索产品或物料" @keyup.enter="search" @clear="search" />
      <ElButton type="primary" @click="search">查询</ElButton>
    </section>
    <ElTable v-table-column-widths="'production.procedure-prices'" v-loading="loading" :data="items" border stripe table-layout="auto" empty-text="暂无可配置项">
      <ElTableColumn label="产品 / 物料" min-width="260">
        <template #default="{ row }"><strong>{{ title(row) }}</strong><div>V{{ row.product_version }} · {{ row.part_no }}</div></template>
      </ElTableColumn>
      <ElTableColumn prop="workshop_name" label="车间" min-width="120" />
      <ElTableColumn label="工艺" min-width="200">
        <template #default="{ row }">{{ procedureNames(row) }}</template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="90" align="center">
        <template #default="{ row }"><ElButton size="small" :disabled="!canManage" @click="open(row)">配置</ElButton></template>
      </ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" layout="prev, pager, next, total" :page-size="pageSize" :total="total" @current-change="load" />
    <ElDialog v-model="dialogVisible" append-to-body width="min(680px, 92vw)" title="配置工艺与单价">
      <div v-if="activeScope" class="dialog-title">{{ title(activeScope) }} · {{ activeScope.workshop_name }}</div>
      <div class="procedure-list">
        <div v-for="(item, index) in draft" :key="item.procedure_id ?? `new-${index}`" class="procedure-row">
          <ElInput v-model="item.procedure_name" :disabled="item.procedure_id !== null" maxlength="200" placeholder="工艺名称" />
          <ElInputNumber v-model="item.unit_price" :min="0" :precision="2" :step="0.1" placeholder="单价" />
          <ElButton :disabled="item.referenced" @click="removeProcedure(index)">删除</ElButton>
        </div>
      </div>
      <ElButton plain @click="addProcedure">添加工艺</ElButton>
      <template #footer><ElButton @click="dialogVisible = false">取消</ElButton><ElButton type="primary" :loading="saving" @click="save">保存</ElButton></template>
    </ElDialog>
  </component>
</template>

<style scoped>
.filter-bar { display: flex; gap: 10px; margin-bottom: 14px; }
.filter-bar .el-input { max-width: 360px; }
.procedure-list { display: grid; gap: 10px; margin: 16px 0; }
.procedure-row { display: grid; grid-template-columns: minmax(0, 1fr) 150px auto; gap: 10px; align-items: center; }
.dialog-title { color: var(--el-text-color-secondary); }
</style>
