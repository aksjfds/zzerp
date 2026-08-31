<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import {
  queryProductionPositionStorageCandidates,
  storeProductionPosition,
} from '../api/productionStorage'
import type { ProductionPositionStorageCandidate } from '../domain/types'

const props = defineProps<{ departmentCode: string }>()
const loading = ref(false)
const submittingKey = ref<string | null>(null)
const items = ref<ProductionPositionStorageCandidate[]>([])
const itemTypeLabels = { part: '普通配件', assembly: '装配体' } as const

async function load() {
  loading.value = true
  try {
    items.value = await queryProductionPositionStorageCandidates(props.departmentCode)
  } catch (error) {
    ElMessage.error(getApiErrorDetail(error)?.message || '可入库物料加载失败')
  } finally {
    loading.value = false
  }
}

async function store(item: ProductionPositionStorageCandidate) {
  try {
    const { value } = await ElMessageBox.prompt(
      `生产计划已完成，当前可用 ${item.available_quantity} 件。入库后不能再用于开工单。`,
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
      `已存入仓库 ${result.quantity} 件，完成状态：${result.completion_status}`,
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
  <section v-loading="loading" class="position-storage">
    <div class="position-storage-heading">
      <div>
        <h2>可入库物料</h2>
        <p>仅展示生产计划已完成、当前节点尚未加工且未被工单占用的配件和装配体。</p>
      </div>
      <ElButton @click="load">刷新</ElButton>
    </div>
    <ElTable v-table-column-widths="'production.position-storage'" :data="items" border stripe table-layout="auto" empty-text="暂无可入库物料">
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
      <ElTableColumn prop="completion_status" label="完成状态" min-width="120" />
      <ElTableColumn prop="available_quantity" label="可入库数量" width="110" align="right" />
      <ElTableColumn label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <ElButton
            link
            type="primary"
            :loading="submittingKey === row.key"
            @click="store(row)"
          >存入仓库</ElButton>
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
