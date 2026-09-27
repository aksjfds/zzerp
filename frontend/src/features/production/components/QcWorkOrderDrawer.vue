<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useClosingSnapshot } from '@/shared/motion/useClosingSnapshot'
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
const loadError = ref('')
const record = ref<ProductionProgressWorkOrder | null>(null)
const { display, closing, beginClose, finishClose } = useClosingSnapshot(visible, () => ({
  record: record.value,
  loading: loading.value,
  error: loadError.value,
}), () => { visible.value = false })
let requestRevision = 0

async function load() {
  const revision = ++requestRevision
  loadError.value = ''
  record.value = null
  if (!props.modelValue || !props.workOrderId) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const result = await queryQcWorkOrderDetail(props.workOrderId)
    if (revision === requestRevision) record.value = result
  } catch (error) {
    if (revision === requestRevision) {
      loadError.value = getApiErrorDetail(error)?.message || '工单记录加载失败'
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
      loadError.value = ''
      record.value = null
    }
  },
  { immediate: true },
)
onScopeDispose(() => { requestRevision += 1 })
</script>

<template>
  <ElDrawer
    ref="drawerRef"
    v-model="visible"
    title="工单和质检记录"
    size="76%"
    destroy-on-close
    class="production-progress-drawer"
    @contextmenu.prevent="closeByContextMenu"
    @close="beginClose"
    @closed="finishClose"
  >
    <div v-loading="display.loading" class="drawer-body" :inert="closing || !visible">
      <LoadErrorAlert v-if="display.error" :message="display.error" :loading="loading" @retry="load" />
      <WorkOrderRecordCard v-else-if="display.record" :record="display.record" />
      <ElEmpty v-else-if="!display.loading" description="请选择工单查看质检记录" />
    </div>
  </ElDrawer>
</template>

<style scoped>
.drawer-body {
  min-height: 360px;
}
</style>
