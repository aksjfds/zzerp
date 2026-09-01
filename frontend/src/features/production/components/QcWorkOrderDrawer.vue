<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import { queryQcWorkOrderDetail } from '../api/qc'
import type { ProductionProgressWorkOrder } from '../domain/productionProgress'
import WorkOrderRecordCard from './WorkOrderRecordCard.vue'

const props = defineProps<{
  modelValue: boolean
  workOrderId: number | null
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})
const drawerRef = ref<{ handleClose: () => void } | null>(null)
const loading = ref(false)
const record = ref<ProductionProgressWorkOrder | null>(null)
let requestRevision = 0

async function load() {
  if (!props.workOrderId) return
  const revision = ++requestRevision
  loading.value = true
  record.value = null
  try {
    const result = await queryQcWorkOrderDetail(props.workOrderId)
    if (revision === requestRevision) record.value = result
  } catch (error) {
    if (revision === requestRevision) {
      ElMessage.error(getApiErrorDetail(error)?.message || '工单记录加载失败')
    }
  } finally {
    if (revision === requestRevision) loading.value = false
  }
}

function closeByContextMenu() {
  drawerRef.value?.handleClose()
}

watch(
  () => [props.modelValue, props.workOrderId] as const,
  ([open]) => {
    if (open) void load()
    else {
      requestRevision += 1
      loading.value = false
      record.value = null
    }
  },
)
</script>

<template>
  <ElDrawer
    ref="drawerRef"
    v-model="visible"
    title="工单和质检记录"
    size="76%"
    destroy-on-close
    modal-class="production-progress-overlay"
    class="production-progress-drawer"
    @contextmenu.prevent="closeByContextMenu"
  >
    <div v-loading="loading" class="drawer-body">
      <WorkOrderRecordCard v-if="record" :record="record" />
      <ElEmpty v-else-if="!loading" description="工单记录未加载" />
    </div>
  </ElDrawer>
</template>

<style scoped>
:global(.el-overlay.is-drawer.production-progress-overlay) {
  --erp-drawer-transition-duration: 300ms;
  background-color: transparent !important;
}

.drawer-body {
  min-height: 360px;
}
</style>
