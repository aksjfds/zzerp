<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { PRODUCTION_PERMISSIONS } from '@/permission/constants'
import { useAuthStore } from '@/stores/auth'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import {
  queryProcedureTagPrices,
  saveProcedureTagPrices,
  type ProcedureTagPricePart,
} from '../api/procedureTagPrices'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
}>(), {
  embedded: false,
  departmentCode: '',
})
const emit = defineEmits<{
  saved: []
}>()
type EditableProcedure = ProcedureTagPricePart['procedures'][number] & {
  tagNames: string[]
  prices: Record<string, number | null>
  saving: boolean
}
type EditablePart = Omit<ProcedureTagPricePart, 'procedures'> & {
  procedures: EditableProcedure[]
}

const departmentNames: Record<string, string> = {
  stamp: '冲压部',
  cnc: '机加部',
  polish: '表面处理部',
}
const route = useRoute()
const authStore = useAuthStore()
const departmentCode = computed(() => String(
  props.departmentCode || route.params.departmentCode || route.meta.departmentCode || '',
))
const departmentName = computed(() => departmentNames[departmentCode.value] || departmentCode.value)
const canManage = computed(() => authStore.hasPermission(PRODUCTION_PERMISSIONS.manage))
const items = ref<EditablePart[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)
const configVisible = ref(false)
const configuringPart = ref<EditablePart>()
const configuringProcedure = ref<EditableProcedure>()
const draftTagNames = ref<string[]>([])
const draftPrices = ref<Record<string, number | null>>({})

function partTitle(part: EditablePart) {
  return [part.factory_code, part.product_name, part.part_name]
    .filter(Boolean)
    .join('-')
}

type PriceTableRow = {
  key: string
  part: EditablePart
  procedure: EditableProcedure
  tagName: string
  price: number | null
  groupSize: number
  firstInGroup: boolean
}

const tableRows = computed<PriceTableRow[]>(() => items.value.flatMap(part => (
  part.procedures.flatMap(procedure => {
    const tagNames = procedure.tagNames.length ? procedure.tagNames : ['']
    return tagNames.map((tagName, index) => ({
      key: [
        part.product_id,
        part.product_version,
        part.origin_flow_node_id,
        procedure.procedure_id,
        tagName || 'empty',
      ].join(':'),
      part,
      procedure,
      tagName,
      price: tagName ? procedure.prices[tagName] ?? null : null,
      groupSize: tagNames.length,
      firstInGroup: index === 0,
    }))
  })
)))

function tableSpan({
  row,
  columnIndex,
}: {
  row: PriceTableRow
  columnIndex: number
}) {
  if (![0, 1, 4].includes(columnIndex)) return [1, 1]
  return row.firstInGroup ? [row.groupSize, 1] : [0, 0]
}

function openConfiguration(part: EditablePart, procedure: EditableProcedure) {
  configuringPart.value = part
  configuringProcedure.value = procedure
  draftTagNames.value = [...procedure.tagNames]
  draftPrices.value = { ...procedure.prices }
  configVisible.value = true
}

async function saveConfiguration() {
  const part = configuringPart.value
  const procedure = configuringProcedure.value
  if (!part || !procedure) return
  const names = [...new Set(draftTagNames.value
    .map(name => name.trim())
    .filter(Boolean))]
  procedure.tagNames = names
  procedure.prices = Object.fromEntries(
    names.map(name => [name, draftPrices.value[name] ?? null]),
  )
  if (await save(part, procedure)) configVisible.value = false
}

function editableParts(data: ProcedureTagPricePart[]): EditablePart[] {
  return data.map(part => ({
    ...part,
    procedures: part.procedures.map(procedure => ({
      ...procedure,
      tagNames: procedure.configured_tags.map(tag => tag.tag_name),
      prices: Object.fromEntries(procedure.configured_tags.map(tag => [
        tag.tag_name,
        tag.unit_price === null ? null : Number(tag.unit_price),
      ])),
      saving: false,
    })),
  }))
}

async function load() {
  loading.value = true
  try {
    const result = await queryProcedureTagPrices(
      departmentCode.value,
      page.value,
      pageSize,
      keyword.value,
    )
    items.value = editableParts(result.data)
    total.value = result.total
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '标记单价配置加载失败')
  } finally {
    loading.value = false
  }
}

async function search() {
  page.value = 1
  await load()
}

async function save(part: EditablePart, procedure: EditableProcedure) {
  const names = [...new Set(procedure.tagNames
    .map(name => name.trim())
    .filter(Boolean))]
  procedure.saving = true
  try {
    await saveProcedureTagPrices(
      departmentCode.value,
      part.product_id,
      part.product_version,
      part.origin_flow_node_id,
      procedure.procedure_id,
      names.map(name => ({
        tag_name: name,
        unit_price: procedure.prices[name] ?? null,
      })),
    )
    ElMessage.success(`${part.part_name} · ${procedure.procedure_name}配置已保存`)
    await load()
    emit('saved')
    return true
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '配置保存失败')
    return false
  } finally {
    procedure.saving = false
  }
}

onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'tag-price-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="departmentName"
      page-title="标记与单价配置"
      description="按配件维护当前部门工艺的标记与计件单价。"
      @refresh="load"
    />
    <section class="filter-bar">
      <ElInput
        v-model="keyword"
        clearable
        placeholder="搜索产品、型号、配件名称或编号"
        @keyup.enter="search"
        @clear="search"
      />
      <ElButton type="primary" @click="search">查询</ElButton>
    </section>
    <ElTable
      v-loading="loading"
      class="price-table"
      :data="tableRows"
      :span-method="tableSpan"
      border
      stripe
      table-layout="auto"
      empty-text="暂无可配置配件"
      row-key="key"
    >
      <ElTableColumn label="配件" min-width="280">
        <template #default="{ row }">
          <div class="part-title">
            <strong>{{ partTitle(row.part) }}</strong>
            <span>
              V{{ row.part.product_version }}
              <template v-if="row.procedure.tags_locked"> · 标记已锁定</template>
            </span>
          </div>
        </template>
      </ElTableColumn>
      <ElTableColumn label="加工工艺" min-width="140">
        <template #default="{ row }">{{ row.procedure.procedure_name }}</template>
      </ElTableColumn>
      <ElTableColumn label="标记" min-width="160">
        <template #default="{ row }">{{ row.tagName || '暂未配置标记' }}</template>
      </ElTableColumn>
      <ElTableColumn label="单价" width="120" align="right">
        <template #default="{ row }">{{ row.price ?? '—' }}</template>
      </ElTableColumn>
      <ElTableColumn label="配置" width="90" align="center">
        <template #default="{ row }">
          <ElButton
            size="small"
            :disabled="!canManage"
            @click="openConfiguration(row.part, row.procedure)"
          >配置</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
    <ElPagination
      v-model:current-page="page"
      class="pagination"
      layout="prev, pager, next, total"
      :page-size="pageSize"
      :total="total"
      @current-change="load"
    />

    <ElDialog
      v-model="configVisible"
      append-to-body
      width="min(640px, 92vw)"
      title="配置标记与单价"
    >
      <div v-if="configuringPart && configuringProcedure" class="config-dialog">
        <div class="config-title">
          <strong>{{ partTitle(configuringPart) }}</strong>
          <span>{{ configuringProcedure.procedure_name }}</span>
        </div>
        <ElForm label-position="top">
          <ElFormItem label="标记">
            <ElSelect
              v-model="draftTagNames"
              placement="top-start"
              :fallback-placements="['top-start', 'top-end']"
              tag-type="danger"
              tag-effect="dark"
              multiple
              filterable
              allow-create
              default-first-option
              clearable
              :disabled="configuringProcedure.tags_locked"
              placeholder="选择或输入标记"
            >
              <ElOption
                v-for="tag in configuringProcedure.available_tags"
                :key="tag.id"
                :label="tag.tag_name"
                :value="tag.tag_name"
              />
            </ElSelect>
          </ElFormItem>
        </ElForm>
        <div v-if="draftTagNames.length" class="config-price-list">
          <div v-for="tagName in draftTagNames" :key="tagName" class="config-price-row">
            <span>{{ tagName }}</span>
            <ElInputNumber
              v-model="draftPrices[tagName]"
              :min="0"
              :precision="2"
              :step="0.1"
              placeholder="单价"
            />
            <em>元 / 件</em>
          </div>
        </div>
        <ElEmpty v-else description="暂未配置标记" :image-size="48" />
      </div>
      <template #footer>
        <ElButton @click="configVisible = false">取消</ElButton>
        <ElButton
          type="primary"
          :disabled="!canManage"
          :loading="configuringProcedure?.saving"
          @click="saveConfiguration"
        >保存</ElButton>
      </template>
    </ElDialog>
  </component>
</template>

<style scoped>
.tag-price-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.filter-bar { display: flex; gap: 10px; margin-bottom: 18px; }
.filter-bar .el-input { max-width: 440px; }
.price-table { width: 100%; min-height: 220px; }
.part-title { display: grid; gap: 2px; min-width: 0; }
.part-title strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.part-title span { color: var(--el-text-color-secondary); font-size: 12px; }
.config-dialog { display: grid; gap: 16px; }
.config-title { display: grid; gap: 4px; }
.config-title span { color: var(--el-text-color-secondary); font-size: 13px; }
.config-dialog :deep(.el-select) { width: 100%; }
.config-price-list { display: grid; gap: 8px; }
.config-price-row { display: grid; grid-template-columns: minmax(120px, 1fr) 180px 58px; gap: 10px; align-items: center; padding: 8px 10px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.config-price-row em { color: var(--el-text-color-secondary); font-size: 12px; font-style: normal; }
.pagination { justify-content: flex-end; margin-top: 18px; }
@media (max-width: 700px) {
  .tag-price-page { padding: 16px; }
  .filter-bar { align-items: stretch; flex-direction: column; }
  .filter-bar .el-input, .filter-bar :deep(.el-button) { width: 100%; max-width: none; }
  .config-price-row { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .tag-price-page { padding: 12px; }
}
</style>
