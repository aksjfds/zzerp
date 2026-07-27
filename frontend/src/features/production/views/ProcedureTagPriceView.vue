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

type EditableProcedure = ProcedureTagPricePart['procedures'][number] & {
  tagNames: string[]
  prices: Record<string, number | null>
  saving: boolean
}
type EditablePart = Omit<ProcedureTagPricePart, 'procedures'> & {
  procedures: EditableProcedure[]
}

const departmentNames: Record<string, string> = {
  stamp: '冲压部门',
  cnc: '机加部门',
  polish: '表面处理部门',
  warehouse: '仓库部门',
}
const route = useRoute()
const authStore = useAuthStore()
const departmentCode = computed(() => String(route.params.departmentCode || ''))
const departmentName = computed(() => departmentNames[departmentCode.value] || departmentCode.value)
const canManage = computed(() => authStore.hasPermission(PRODUCTION_PERMISSIONS.manage))
const items = ref<EditablePart[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const pageSize = 20
const total = ref(0)

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
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '配置保存失败')
  } finally {
    procedure.saving = false
  }
}

onMounted(load)
</script>

<template>
  <main class="tag-price-page">
    <DepartmentPageHeader
      :department-name="departmentName"
      description="按配件维护当前部门工艺的标记与计件单价。"
      :back-path="`/${departmentCode}`"
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
    <section v-loading="loading" class="part-list">
      <article v-for="part in items" :key="`${part.product_id}:${part.product_version}:${part.origin_flow_node_id}`" class="part-card">
        <header>
          <div>
            <strong>{{ part.part_no === part.part_name ? part.part_name : `${part.part_no} - ${part.part_name}` }}</strong>
            <span>{{ part.product_name }} · {{ part.factory_code }} · V{{ part.product_version }}</span>
          </div>
        </header>
        <div
          v-for="procedure in part.procedures"
          :key="procedure.procedure_id"
          class="procedure-config"
        >
          <h3>{{ procedure.procedure_name }}</h3>
          <ElSelect
            v-model="procedure.tagNames"
            placement="top-start"
            :fallback-placements="['top-start', 'top-end']"
            tag-type="danger"
            tag-effect="dark"
            multiple
            filterable
            allow-create
            default-first-option
            clearable
            :disabled="!canManage || procedure.tags_locked"
            placeholder="选择或输入该配件必做标记"
          >
            <ElOption
              v-for="tag in procedure.available_tags"
              :key="tag.id"
              :label="tag.tag_name"
              :value="tag.tag_name"
            />
          </ElSelect>
          <p v-if="procedure.tags_locked" class="locked-hint">已开过工单，必做标记已锁定，仅可修改单价。</p>
          <div v-if="procedure.tagNames.length" class="price-list">
            <div v-for="tagName in procedure.tagNames" :key="tagName" class="price-row">
              <span>{{ tagName }}</span>
              <ElInputNumber
                v-model="procedure.prices[tagName]"
                :disabled="!canManage"
                :min="0"
                :precision="2"
                :step="0.1"
                placeholder="未配置单价"
              />
              <em>元 / 件</em>
            </div>
          </div>
          <ElEmpty v-else description="暂未配置标记" :image-size="48" />
          <ElButton
            v-if="canManage"
            type="primary"
            :loading="procedure.saving"
            @click="save(part, procedure)"
          >保存此工艺</ElButton>
        </div>
      </article>
      <ElEmpty v-if="!loading && !items.length" description="暂无可配置配件" />
    </section>
    <ElPagination
      v-model:current-page="page"
      class="pagination"
      layout="prev, pager, next, total"
      :page-size="pageSize"
      :total="total"
      @current-change="load"
    />
  </main>
</template>

<style scoped>
.tag-price-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--md-surface); }
.filter-bar { display: flex; gap: 10px; margin-bottom: 18px; }
.filter-bar .el-input { max-width: 440px; }
.part-list { display: grid; gap: 16px; min-height: 220px; }
.part-card { padding: 20px; border: 1px solid var(--md-outline-variant); border-radius: var(--erp-radius-lg); background: var(--md-surface-container-lowest); box-shadow: var(--erp-shadow-sm); }
.part-card header div { display: grid; gap: 5px; }
.part-card header strong { font-size: 17px; }
.part-card header span { color: var(--el-text-color-secondary); font-size: 13px; }
.procedure-config { margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--erp-border); }
.procedure-config h3 { margin: 0 0 12px; font-size: 15px; }
.procedure-config > .el-select { width: min(680px, 100%); }
.locked-hint { margin: 8px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.price-list { display: grid; gap: 8px; margin: 12px 0; }
.price-row { display: grid; grid-template-columns: minmax(120px, 1fr) 180px 58px; gap: 10px; align-items: center; max-width: 680px; padding: 10px 12px; border-radius: var(--erp-radius); background: var(--md-surface-container-low); }
.price-row em { color: var(--el-text-color-secondary); font-size: 12px; font-style: normal; }
.pagination { justify-content: flex-end; margin-top: 18px; }
@media (max-width: 700px) {
  .tag-price-page { padding: 16px; }
  .filter-bar { align-items: stretch; flex-direction: column; }
  .filter-bar .el-input, .filter-bar :deep(.el-button) { width: 100%; max-width: none; }
  .part-card { padding: 16px; }
  .price-row { grid-template-columns: 1fr; }
}
@media (max-width: 480px) { .tag-price-page { padding: 12px; } .part-card { padding: 12px; border-radius: var(--erp-radius); } }
</style>
