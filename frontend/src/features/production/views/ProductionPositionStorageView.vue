<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import {
  queryDepartmentMaterials,
  storeProductionPosition,
} from '../api/productionStorage'
import type { DepartmentMaterialPosition } from '../domain/types'

const props = defineProps<{ departmentCode: string }>()
const loading = ref(false)
const loadError = ref('')
let loadRevision = 0
const submittingKey = ref<string | null>(null)
const items = ref<DepartmentMaterialPosition[]>([])
const itemTypeLabels = { part: '普通配件', assembly: '装配体' } as const

async function load() {
  const revision = ++loadRevision
  loading.value = true
  loadError.value = ''
  items.value = []
  try {
    const result = await queryDepartmentMaterials(props.departmentCode)
    if (revision === loadRevision) items.value = result
  } catch (error) {
    if (revision === loadRevision) loadError.value = getApiErrorDetail(error)?.message || '物料加载失败'
  } finally {
    if (revision === loadRevision) loading.value = false
  }
}

async function store(item: DepartmentMaterialPosition) {
  try {
    const { value } = await ElMessageBox.prompt(
      `当前可用 ${item.available_quantity} 件。入库后不能再用于开工单。`,
      '当前物料存入仓库',
      {
        inputValue: String(item.available_quantity),
        inputPattern: /^[1-9]\d*$/,
        inputErrorMessage: '请输入正整数',
        confirmButtonText: '确认入库',
        cancelButtonText: '取消',
      },
    )
    const quantity = Number(value)
    if (!Number.isInteger(quantity) || quantity <= 0 || quantity > item.available_quantity) {
      ElMessage.warning(`入库数量必须为 1 到 ${item.available_quantity} 的整数`)
      return
    }
    submittingKey.value = item.key
    const result = await storeProductionPosition(props.departmentCode, item, quantity)
    ElMessage.success(
      `已存入仓库 ${result.quantity} 件，加工情况：${result.processing_status}`,
    )
    await load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorDetail(error)?.message || '存入仓库失败')
    }
  } finally {
    submittingKey.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="position-storage">
    <div class="position-storage-heading">
      <div>
        <h2>当前物料</h2>
        <p>展示当前部门的配件和装配体，包含已被工单占用的数量。</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <LoadErrorAlert v-if="loadError" :message="loadError" :loading="loading" @retry="load" />
    <ElTable v-else v-table-column-widths="'production.position-storage'" v-loading="loading" :data="items" border stripe table-layout="auto" empty-text="当前部门暂无物料">
      <ElTableColumn prop="customer_order_no" label="订单编号" min-width="140" />
      <ElTableColumn label="产品" min-width="190">
        <template #default="{ row }">
          {{ row.product_code }} · {{ row.product_name }} · V{{ row.product_version }}
        </template>
      </ElTableColumn>
      <ElTableColumn label="类型" width="100">
        <template #default="{ row }">{{ itemTypeLabels[row.item_type as keyof typeof itemTypeLabels] }}</template>
      </ElTableColumn>
      <ElTableColumn prop="item_code" label="编号" min-width="130" />
      <ElTableColumn prop="item_name" label="名称" min-width="160" />
      <ElTableColumn prop="current_node_label" label="所在节点" min-width="130" />
      <ElTableColumn prop="processing_status" label="加工情况" min-width="180" />
      <ElTableColumn prop="on_hand_quantity" label="当前数量" width="105" align="right" />
      <ElTableColumn prop="occupied_quantity" label="工单占用" width="105" align="right" />
      <ElTableColumn prop="available_quantity" label="可用数量" width="95" align="right" />
      <ElTableColumn label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <ElButton
            v-if="row.available_quantity > 0"
            link
            type="primary"
            :loading="submittingKey === row.key"
            @click="store(row)"
          >存入仓库</ElButton>
          <ElTag v-else type="info" effect="plain" size="small">已被工单占用</ElTag>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.position-storage { min-height: 240px; }
.position-storage-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.position-storage-heading h2 { margin: 0 0 5px; font-size: 20px; }
.position-storage-heading p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
</style>
