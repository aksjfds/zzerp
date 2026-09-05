<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import DepartmentPageHeader from '@/shared/layout/DepartmentPageHeader.vue'
import {
  cancelProcedurePriceConfirmation,
  confirmProcedurePrices,
  queryProcedurePrices,
  queryProcedurePriceRevisions,
  saveProcedurePrices,
  saveTemporaryWorkOrderPrice,
} from '../api/procedurePrices'
import type {
  ProcedurePriceItem,
  ProcedurePriceListItem,
  ProcedurePriceScope,
  ProcedurePriceRevision,
  TemporaryWorkOrderPriceItem,
} from '../domain/procedurePrices'

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
type ProcedurePriceTreeParent = {
  row_type: 'group'
  row_key: string
  product_id: number
  product_version: number
  product_name: string
  factory_code: string
  part_name: string
  part_no: string
  process_rows: ProcedurePriceProcessRow[]
}
type FormalProcedurePriceRow = {
  row_type: 'process'
  price_type: 'formal'
  row_key: string
  is_last_child: boolean
  scope: ProcedurePriceScope
  procedure: ProcedurePriceItem | null
}
type TemporaryProcedurePriceRow = {
  row_type: 'process'
  price_type: 'temporary'
  row_key: string
  is_last_child: boolean
  item: TemporaryWorkOrderPriceItem
}
type ProcedurePriceProcessRow = FormalProcedurePriceRow | TemporaryProcedurePriceRow
type ProcedurePriceTreeRow = ProcedurePriceTreeParent | ProcedurePriceProcessRow
const route = useRoute()
const authStore = useAuthStore()
const departmentCode = computed(() => String(
  props.departmentCode || route.params.departmentCode || route.meta.departmentCode || '',
))
const departmentName = computed(() => authStore.department || departmentCode.value || '生产部门')
const canManage = computed(() => authStore.hasPermission(PRODUCTION_PERMISSIONS.manage))
const items = ref<ProcedurePriceListItem[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const dialogVisible = ref(false)
const activeScope = ref<ProcedurePriceScope>()
const draft = ref<DraftProcedure[]>([])
const saving = ref(false)
const confirming = ref(false)
const cancellingConfirmation = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyItems = ref<ProcedurePriceRevision[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const temporaryPriceDrafts = ref<Record<number, number | null>>({})
const savingTemporaryWorkOrderId = ref<number | null>(null)
const treeRows = computed<ProcedurePriceTreeRow[]>(() => {
  const groups = new Map<string, ProcedurePriceTreeParent>()
  items.value.forEach(item => {
    const groupKey = [
      item.product_id,
      item.product_version,
      item.origin_flow_node_id,
    ].join(':')
    let group = groups.get(groupKey)
    if (!group) {
      group = {
        row_type: 'group',
        row_key: `group:${groupKey}`,
        product_id: item.product_id,
        product_version: item.product_version,
        product_name: item.product_name,
        factory_code: item.factory_code,
        part_name: item.part_name,
        part_no: item.part_no,
        process_rows: [],
      }
      groups.set(groupKey, group)
    }
    if (isTemporaryItem(item)) {
      group.process_rows.push({
        row_type: 'process',
        price_type: 'temporary',
        row_key: `temporary:${item.work_order_id}`,
        is_last_child: false,
        item,
      })
      return
    }
    const procedures = item.procedures.length ? item.procedures : [null]
    procedures.forEach(procedure => {
      group.process_rows.push({
        row_type: 'process',
        price_type: 'formal',
        row_key: `formal:${item.product_id}:${item.product_version}:${item.origin_flow_node_id}:${item.flow_node_id}:${procedure?.procedure_id ?? 'unconfigured'}`,
        is_last_child: false,
        scope: item,
        procedure,
      })
    })
  })
  return [...groups.values()].flatMap(group => [
    group,
    ...group.process_rows.map((row, index) => ({
      ...row,
      is_last_child: index === group.process_rows.length - 1,
    })),
  ])
})

function isGroup(item: ProcedurePriceTreeRow): item is ProcedurePriceTreeParent {
  return item.row_type === 'group'
}
function isTemporaryItem(item: ProcedurePriceListItem): item is TemporaryWorkOrderPriceItem {
  return item.row_type === 'temporary'
}
function isTemporaryProcess(row: ProcedurePriceTreeRow): row is TemporaryProcedurePriceRow {
  return row.row_type === 'process' && row.price_type === 'temporary'
}
function isFormalProcess(row: ProcedurePriceTreeRow): row is FormalProcedurePriceRow {
  return row.row_type === 'process' && row.price_type === 'formal'
}
function title(scope: ProcedurePriceListItem) {
  return `${scope.factory_code}-${scope.product_name}-${scope.part_name}`
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
  if (activeScope.value?.confirmed) return
  draft.value.push({ procedure_id: null, procedure_name: '', unit_price: null, referenced: false })
}
function removeProcedure(index: number) {
  if (!activeScope.value?.confirmed && !draft.value[index]?.referenced) draft.value.splice(index, 1)
}
async function load() {
  loading.value = true
  try {
    const result = await queryProcedurePrices(
      departmentCode.value, page.value, pageSize, keyword.value,
    )
    items.value = result.data
    total.value = result.total
    temporaryPriceDrafts.value = Object.fromEntries(
      result.data.filter(isTemporaryItem).map(item => [
        item.work_order_id,
        item.unit_price === null ? null : Number(item.unit_price),
      ]),
    )
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
async function refreshAll() {
  await load()
}
async function openHistory(pageNumber = 1) {
  historyPage.value = pageNumber
  historyVisible.value = true
  historyLoading.value = true
  try {
    const result = await queryProcedurePriceRevisions(departmentCode.value, pageNumber)
    historyItems.value = result.data
    historyTotal.value = result.total
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '单价变更记录加载失败')
  } finally {
    historyLoading.value = false
  }
}
function priceValue(value: number | string | null) {
  return value === null ? '未配置' : `¥ ${Number(value).toFixed(2)}`
}
async function saveTemporaryPrice(item: TemporaryWorkOrderPriceItem) {
  savingTemporaryWorkOrderId.value = item.work_order_id
  try {
    await saveTemporaryWorkOrderPrice(
      departmentCode.value,
      item.work_order_id,
      temporaryPriceDrafts.value[item.work_order_id] ?? null,
    )
    ElMessage.success('临时工单单价已保存')
    await load()
    emit('saved')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '临时工单单价保存失败')
  } finally {
    savingTemporaryWorkOrderId.value = null
  }
}
function temporaryStatus(item: TemporaryWorkOrderPriceItem) {
  if (item.status === 'closed') return { label: '已结单', type: 'success' as const }
  if (item.status === 'cancelled') return { label: '已取消', type: 'info' as const }
  return { label: '进行中', type: 'warning' as const }
}
function formalPriceText(procedure: ProcedurePriceItem | null) {
  if (!procedure) return '—'
  return procedure.unit_price === null ? '未配置' : `¥ ${Number(procedure.unit_price).toFixed(2)}`
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
    ElMessage.success(scope.confirmed ? '单价已保存' : '配置草稿已保存')
    await load()
    emit('saved')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
async function confirmConfiguration() {
  const scope = activeScope.value
  if (!scope || scope.confirmed) return
  const names = draft.value.map(item => item.procedure_name.trim())
  if (!names.length || names.some(name => !name)) {
    ElMessage.warning('至少配置一个工艺后才能确认')
    return
  }
  if (new Set(names).size !== names.length) {
    ElMessage.warning('同一车间不能重复配置同名工艺')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确认后不能直接新增、删除或更换工艺；未开过工单时可取消确认，单价仍可调整。确认当前工艺配置？',
      '确认工艺配置',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  confirming.value = true
  try {
    await confirmProcedurePrices(departmentCode.value, scope, draft.value.map((item, index) => ({
      procedure_id: item.procedure_id,
      procedure_name: names[index]!,
      unit_price: item.unit_price,
    })))
    dialogVisible.value = false
    ElMessage.success('工艺配置已确认')
    await load()
    emit('saved')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '确认失败')
  } finally {
    confirming.value = false
  }
}
async function cancelConfirmation() {
  const scope = activeScope.value
  if (!scope?.confirmed || !scope.can_cancel) return
  try {
    await ElMessageBox.confirm(
      '取消确认后，工艺清单将恢复可编辑。确认取消当前工艺配置？',
      '取消工艺确认',
      { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '返回' },
    )
  } catch {
    return
  }
  cancellingConfirmation.value = true
  try {
    await cancelProcedurePriceConfirmation(departmentCode.value, scope)
    dialogVisible.value = false
    ElMessage.success('已取消工艺确认')
    await load()
    emit('saved')
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '取消确认失败')
  } finally {
    cancellingConfirmation.value = false
  }
}
onMounted(() => {
  void load()
})
watch(
  () => route.query.tab,
  tab => {
    if (props.embedded && tab === 'tag-prices') void refreshAll()
  },
)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'procedure-price-page': !embedded }">
    <DepartmentPageHeader v-if="!embedded" :department-name="departmentName" page-title="工艺与单价配置" description="维护正式工艺配置及临时工单独立单价。" @refresh="refreshAll" />
    <section class="filter-bar">
      <ElInput v-model="keyword" clearable placeholder="搜索正式产品/物料或临时工单/工艺" @keyup.enter="search" @clear="search" />
      <ElButton type="primary" @click="search">查询</ElButton>
      <ElButton @click="openHistory()">单价记录</ElButton>
    </section>
    <ElTable
      v-table-column-widths="'production.procedure-prices'"
      v-loading="loading"
      :data="treeRows"
      row-key="row_key"
      border
      stripe
      table-layout="auto"
      empty-text="暂无可配置项"
    >
      <ElTableColumn label="产品 / 物料 / 工艺" min-width="290">
        <template #default="{ row }">
          <div v-if="isGroup(row)" class="material-cell">
            <span class="tree-name material-name">
              <span class="directory-icon folder-icon" aria-hidden="true" />
              <strong>{{ row.factory_code }}-{{ row.product_name }}</strong>
            </span>
            <span class="material-detail">V{{ row.product_version }} · {{ row.part_no }} {{ row.part_name }}</span>
          </div>
          <div v-else class="process-cell" :class="{ 'has-next': !row.is_last_child }">
            <span class="tree-name process-branch" :class="{ 'is-last': row.is_last_child }">
              <span class="directory-icon file-icon" aria-hidden="true" />
              <ElPopover v-if="isTemporaryProcess(row)" placement="bottom-start" trigger="click" :width="300">
                <template #reference>
                  <ElLink type="primary" :underline="false">{{ row.item.procedure_name }}</ElLink>
                </template>
                <div class="temporary-work-order-popover">
                  <strong>工单 {{ row.item.work_order_no }}</strong>
                  <span>车间：{{ row.item.workshop_name }}</span>
                  <span>状态：{{ temporaryStatus(row.item).label }}</span>
                </div>
              </ElPopover>
              <span v-else>{{ row.procedure?.procedure_name || '尚未配置工艺' }}</span>
              <ElTag :type="isTemporaryProcess(row) ? 'warning' : 'primary'" effect="plain" size="small">
                {{ isTemporaryProcess(row) ? '临时' : '正式' }}
              </ElTag>
            </span>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="车间" min-width="120">
        <template #default="{ row }">{{ isGroup(row) ? '—' : isTemporaryProcess(row) ? row.item.workshop_name : row.scope.workshop_name }}</template>
      </ElTableColumn>
      <ElTableColumn label="状态" min-width="100" align="center">
        <template #default="{ row }">
          <ElTag v-if="isTemporaryProcess(row)" :type="temporaryStatus(row.item).type">{{ temporaryStatus(row.item).label }}</ElTag>
          <ElTag v-else-if="isFormalProcess(row)" :type="row.scope.confirmed ? 'success' : 'info'">{{ row.scope.confirmed ? '已确认' : '草稿' }}</ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn label="单价" min-width="155">
        <template #default="{ row }">
          <ElInputNumber v-if="isTemporaryProcess(row)" v-model="temporaryPriceDrafts[row.item.work_order_id]" :min="0" :precision="2" :step="0.1" placeholder="未配置" />
          <span v-else-if="isFormalProcess(row)">{{ formalPriceText(row.procedure) }}</span>
          <span v-else>—</span>
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" min-width="90" align="center">
        <template #default="{ row }">
          <ElButton v-if="isTemporaryProcess(row)" type="primary" link :disabled="!canManage" :loading="savingTemporaryWorkOrderId === row.item.work_order_id" @click="saveTemporaryPrice(row.item)">保存</ElButton>
          <ElButton v-else-if="isFormalProcess(row)" size="small" :disabled="!canManage" @click="open(row.scope)">配置</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
    <ElPagination v-model:current-page="page" layout="prev, pager, next, total" :page-size="pageSize" :total="total" @current-change="load" />
    <ElDialog v-model="dialogVisible" append-to-body width="min(680px, 92vw)" title="配置工艺与单价">
      <div v-if="activeScope" class="dialog-title">
        <span>{{ title(activeScope) }} · {{ activeScope.workshop_name }}</span>
        <ElTag :type="activeScope.confirmed ? 'success' : 'info'">{{ activeScope.confirmed ? '工艺已确认' : '配置草稿' }}</ElTag>
      </div>
      <div class="procedure-list">
        <div v-for="(item, index) in draft" :key="item.procedure_id ?? `new-${index}`" class="procedure-row">
          <ElInput v-model="item.procedure_name" :disabled="activeScope?.confirmed || item.procedure_id !== null" maxlength="200" placeholder="工艺名称" />
          <ElInputNumber v-model="item.unit_price" :min="0" :precision="2" :step="0.1" placeholder="单价" />
          <ElButton :disabled="activeScope?.confirmed || item.referenced" @click="removeProcedure(index)">删除</ElButton>
        </div>
      </div>
      <ElButton v-if="!activeScope?.confirmed" plain @click="addProcedure">添加工艺</ElButton>
      <template #footer>
        <ElButton @click="dialogVisible = false">关闭</ElButton>
        <ElButton
          v-if="activeScope?.confirmed"
          plain
          type="danger"
          :disabled="!activeScope.can_cancel"
          :loading="cancellingConfirmation"
          :title="activeScope.can_cancel ? '' : '当前配置已经开过工单，不能取消确认'"
          @click="cancelConfirmation"
        >取消确认</ElButton>
        <ElButton :loading="saving" @click="save">{{ activeScope?.confirmed ? '保存单价' : '保存草稿' }}</ElButton>
        <ElButton v-if="!activeScope?.confirmed" type="primary" :loading="confirming" @click="confirmConfiguration">确认工艺</ElButton>
      </template>
    </ElDialog>
    <ElDrawer v-model="historyVisible" title="单价变更记录" size="min(760px, 92vw)" append-to-body>
      <ElTable v-loading="historyLoading" :data="historyItems" border table-layout="auto">
        <ElTableColumn prop="target_label" label="工艺" min-width="260" />
        <ElTableColumn label="变更" min-width="170">
          <template #default="{ row }">{{ priceValue(row.previous_unit_price) }} → {{ priceValue(row.new_unit_price) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="actor_username" label="操作人" min-width="100" />
        <ElTableColumn prop="created_at" label="时间" min-width="160" />
      </ElTable>
      <ElPagination v-model:current-page="historyPage" layout="prev, pager, next, total" :page-size="50" :total="historyTotal" @current-change="openHistory" />
    </ElDrawer>
  </component>
</template>

<style scoped>
.filter-bar { display: flex; gap: 10px; margin-bottom: 14px; }
.filter-bar .el-input { max-width: 360px; }
.tree-name { display: inline-flex; align-items: center; gap: 8px; }
.material-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }
.material-detail { padding-left: 25px; color: var(--md-on-surface-variant); }
.process-cell { position: relative; }
.directory-icon { position: relative; display: inline-block; flex: 0 0 auto; box-sizing: border-box; color: var(--el-color-primary); }
.folder-icon { width: 17px; height: 13px; margin-top: 2px; border: 1.5px solid currentcolor; border-radius: 2px; }
.folder-icon::before { position: absolute; top: -5px; left: -1.5px; width: 8px; height: 5px; border: 1.5px solid currentcolor; border-bottom: 0; border-radius: 2px 2px 0 0; content: ''; }
.file-icon { width: 13px; height: 16px; border: 1.5px solid var(--md-outline); border-radius: 2px; }
.file-icon::after { position: absolute; top: 2px; right: 2px; width: 4px; height: 4px; border-top: 1px solid var(--md-outline); border-right: 1px solid var(--md-outline); content: ''; }
.process-branch { position: relative; min-height: 28px; padding-left: 30px; }
.process-branch::before { position: absolute; top: -24px; bottom: 50%; left: 8px; width: 15px; border-bottom: 1px solid var(--md-outline-variant); border-left: 1px solid var(--md-outline-variant); content: ''; }
.process-cell.has-next::after { position: absolute; top: 14px; bottom: -24px; left: 8px; border-left: 1px solid var(--md-outline-variant); content: ''; }
.temporary-work-order-popover { display: grid; gap: 8px; }
.procedure-list { display: grid; gap: 10px; margin: 16px 0; }
.procedure-row { display: grid; grid-template-columns: minmax(0, 1fr) 150px auto; gap: 10px; align-items: center; }
.dialog-title { display: flex; justify-content: space-between; gap: 12px; align-items: center; color: var(--el-text-color-secondary); }
</style>
