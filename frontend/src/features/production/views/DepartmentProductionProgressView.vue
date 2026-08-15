<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'
import { getApiErrorDetail } from '@/api/request'
import { getDepartmentModule } from '@/features/departments/registry'
import DepartmentPageHeader from '../components/DepartmentPageHeader.vue'
import ProductionProgressItemDrawer from '../components/ProductionProgressItemDrawer.vue'
import {
  queryDepartmentProductionProgress,
  type DepartmentProductionProgressItem,
} from '../api/productionProgress'
import '../styles/workspace.css'

const props = withDefaults(defineProps<{
  embedded?: boolean
  departmentCode?: string
}>(), {
  embedded: false,
  departmentCode: '',
})
const route = useRoute()
const departmentCode = computed(
  () => String(props.departmentCode || route.meta.departmentCode || ''),
)
const department = computed(() => getDepartmentModule(departmentCode.value))
const items = ref<DepartmentProductionProgressItem[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 50
const total = ref(0)
const selectedItem = ref<DepartmentProductionProgressItem | null>(null)
const detailVisible = ref(false)

type ProgressTreeRow = DepartmentProductionProgressItem & {
  row_key: string
  is_material: boolean
  has_materials: boolean
  process_rowspan: number
}

const ASSEMBLY_MERGED_COLUMNS = new Set([
  'processing_workshop',
  'task_quantity',
  'completed_quantity',
  'remark',
])

const treeItems = computed<ProgressTreeRow[]>(() => items.value.flatMap((item) => {
  const parent: ProgressTreeRow = {
    ...item,
    row_key: `task:${item.production_plan_item_id}:${item.flow_node_id || item.processing_workshop}`,
    is_material: false,
    has_materials: item.material_arrivals.length > 0,
    process_rowspan: departmentCode.value === 'assembly'
      ? item.material_arrivals.length + 1
      : 1,
  }
  const materials: ProgressTreeRow[] = item.material_arrivals.map((material, index) => ({
      production_plan_item_id: item.production_plan_item_id,
      production_item_id: null,
      flow_node_id: null,
      part_no: material.material_no,
      part_name: material.material_name,
      processing_workshop: '',
      task_quantity: material.task_quantity,
      arrived_quantity: material.arrived_quantity,
      material_arrivals: [],
      completed_quantity: 0,
      remark: '',
      row_key: `material:${item.production_plan_item_id}:${material.material_type}:${material.material_no}:${index}`,
      is_material: true,
      has_materials: false,
      process_rowspan: 0,
  }))
  return [parent, ...materials]
}))

async function load() {
  if (!departmentCode.value) return
  loading.value = true
  try {
    const result = await queryDepartmentProductionProgress(
      departmentCode.value,
      page.value,
      pageSize,
      keyword.value.trim(),
    )
    items.value = result.data
    total.value = result.total
  } catch (error) {
    ElMessage.error(
      getApiErrorDetail(error)?.message || '生产任务加载失败',
    )
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function clear() {
  keyword.value = ''
  search()
}

function displayWorkshopName(name: string) {
  return name.replace(/车间$/, '') || '—'
}

function openDetail(item: DepartmentProductionProgressItem) {
  selectedItem.value = item
  detailVisible.value = true
}

function productionTaskSpan({
  row,
  column,
}: {
  row: ProgressTreeRow
  column: { property?: string }
}) {
  if (
    departmentCode.value !== 'assembly'
    || !column.property
    || !ASSEMBLY_MERGED_COLUMNS.has(column.property)
  ) return [1, 1]
  return row.is_material ? [0, 0] : [row.process_rowspan, 1]
}

onMounted(load)
</script>

<template>
  <component :is="embedded ? 'section' : 'main'" :class="{ 'production-page': !embedded }">
    <DepartmentPageHeader
      v-if="!embedded"
      :department-name="department?.name || '生产部门'"
      page-title="生产任务"
      description="生产计划创建后即可查看本部门需要生产的配件或装配体。"
      @refresh="load"
    />

    <section class="progress-panel">
      <div class="progress-toolbar">
        <ElInput
          v-model="keyword"
          clearable
          placeholder="搜索物料编号、物料名称或订单号"
          @clear="search"
          @keyup.enter="search"
        />
        <ElButton type="primary" @click="search">查询</ElButton>
        <ElButton @click="clear">清空</ElButton>
      </div>

      <ElTable
        v-loading="loading"
        :data="treeItems"
        row-key="row_key"
        border
        stripe
        table-layout="auto"
        empty-text="暂无生产任务"
        :span-method="productionTaskSpan"
      >
        <ElTableColumn prop="part_name" label="配件/装配体" min-width="210">
          <template #default="{ row }">
            <span v-if="row.is_material" class="tree-name material-name">
              <span class="directory-icon file-icon" aria-hidden="true" />
              <span>{{ row.part_name }}</span>
            </span>
            <ElLink
              v-else
              class="tree-name"
              type="primary"
              :underline="false"
              @click="openDetail(row)"
            >
              <span
                v-if="row.has_materials"
                class="directory-icon folder-icon"
                aria-hidden="true"
              />
              <span>{{ row.part_name }}</span>
            </ElLink>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="part_no" label="物料编号" min-width="150" />
        <ElTableColumn prop="processing_workshop" label="加工工艺" min-width="160">
          <template #default="{ row }">
            {{ displayWorkshopName(row.processing_workshop) }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="task_quantity" label="任务数" min-width="90" align="right">
          <template #default="{ row }">
            {{ row.task_quantity }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="到货数" min-width="100" align="right">
          <template #default="{ row }">
            {{ row.has_materials ? '—' : row.arrived_quantity }}
          </template>
        </ElTableColumn>
        <ElTableColumn prop="completed_quantity" label="完成数" min-width="110" align="right">
          <template #default="{ row }">
            <span v-if="!row.is_material" class="completed">
              {{ row.completed_quantity }}
            </span>
            <span v-else>—</span>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="remark" label="备注" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </ElTableColumn>
      </ElTable>

      <ElPagination
        v-model:current-page="page"
        class="progress-pagination"
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="load"
      />
    </section>

    <ProductionProgressItemDrawer
      v-model="detailVisible"
      :department-code="departmentCode"
      :item="selectedItem"
    />
  </component>
</template>

<style scoped>
.progress-panel {
  padding: 18px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--erp-radius-lg);
  background: var(--md-surface-container-lowest);
  box-shadow: var(--erp-shadow-sm);
}

.progress-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 520px) auto auto;
  gap: 10px;
  margin-bottom: 16px;
}

.completed {
  color: #16a34a;
  font-weight: 700;
}

.tree-name {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.directory-icon {
  position: relative;
  display: inline-block;
  flex: 0 0 auto;
  width: 16px;
  height: 13px;
  box-sizing: border-box;
}

.folder-icon {
  margin-top: 2px;
  border: 1.5px solid currentcolor;
  border-radius: 2px;
}

.folder-icon::before {
  position: absolute;
  top: -5px;
  left: -1.5px;
  width: 7px;
  height: 5px;
  border: 1.5px solid currentcolor;
  border-bottom: 0;
  border-radius: 2px 2px 0 0;
  content: '';
}

.file-icon {
  width: 13px;
  height: 16px;
  border: 1.5px solid currentcolor;
  border-radius: 2px;
}

.file-icon::after {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 4px;
  height: 4px;
  border-top: 1px solid currentcolor;
  border-right: 1px solid currentcolor;
  content: '';
}

.material-name {
  position: relative;
  padding-left: 28px;
  color: var(--md-on-surface-variant);
}

.material-name::before {
  position: absolute;
  top: -20px;
  bottom: 50%;
  left: 8px;
  width: 14px;
  border-bottom: 1px solid var(--md-outline-variant);
  border-left: 1px solid var(--md-outline-variant);
  content: '';
}

.progress-pagination {
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 680px) {
  .progress-panel {
    padding: 12px;
  }

  .progress-toolbar {
    grid-template-columns: 1fr;
  }

  .progress-toolbar :deep(.el-button) {
    width: 100%;
    margin: 0;
  }
}
</style>
