<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getApiErrorDetail } from '@/api/request'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import {
  queryDepartmentMovements, recordDepartmentMovement,
  type DepartmentMovement, type DepartmentMovementInput, type DepartmentWorkOrder,
} from '../api/plans'

const props = defineProps<{ order: DepartmentWorkOrder; direction?: 'receipt' | 'issue' }>()
const emit = defineEmits<{ close: []; changed: [] }>()
const visible = ref(true)
const quantity = ref<number>()
const note = ref('')
const saving = ref(false)
const saveError = ref('')
const rows = ref<DepartmentMovement[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref('')
const title = computed(() => props.direction === 'receipt' ? '到料登记' : props.direction === 'issue' ? '出料登记' : '到料／出料流水')
let active = true
let revision = 0
let pending: DepartmentMovementInput | undefined

async function load() {
  const current = ++revision
  loading.value = true
  error.value = ''
  rows.value = []
  try {
    const result = await queryDepartmentMovements(props.order.id, page.value)
    if (!active || current !== revision) return
    rows.value = result.data
    total.value = result.total
  } catch (cause) {
    if (active && current === revision) error.value = getApiErrorDetail(cause)?.message || '流水加载失败'
  } finally { if (active && current === revision) loading.value = false }
}

async function save() {
  if (saving.value || !props.direction) return
  if (!Number.isSafeInteger(quantity.value) || !quantity.value || quantity.value <= 0) {
    saveError.value = '请输入正整数数量'
    return
  }
  const value = { direction: props.direction, quantity: quantity.value, note: note.value.trim() }
  if (!pending || pending.direction !== value.direction || pending.quantity !== value.quantity || pending.note !== value.note) {
    pending = { ...value, request_id: crypto.randomUUID() }
  }
  saving.value = true
  saveError.value = ''
  try {
    await recordDepartmentMovement(props.order.id, pending)
    if (!active) return
    emit('changed')
    visible.value = false
  } catch (cause) {
    if (active) saveError.value = getApiErrorDetail(cause)?.message || '登记失败，请重试；相同内容重试不会重复记账'
  } finally { if (active) saving.value = false }
}

function beforeClose(done: () => void) { if (!saving.value) done() }
onMounted(load)
onBeforeUnmount(() => { active = false; revision += 1 })
</script>

<template>
  <ElDialog v-model="visible" :title="title" width="min(1000px, 96vw)" :before-close="beforeClose" :close-on-click-modal="!saving" :close-on-press-escape="!saving" :show-close="!saving" @closed="emit('close')">
    <p>{{ order.order_no }} · {{ order.department_name }} · {{ order.part_name }}</p>
    <ElForm v-if="direction" label-width="80px" @submit.prevent="save">
      <ElFormItem label="数量"><ElInputNumber v-model="quantity" :min="1" :max="Number.MAX_SAFE_INTEGER" :precision="0" :step="1" :disabled="saving" controls-position="right" /></ElFormItem>
      <ElFormItem label="备注"><ElInput v-model="note" type="textarea" :rows="2" maxlength="1000" show-word-limit :disabled="saving" /></ElFormItem>
      <p class="movement-note">支持分批登记；到料和出料独立记录，不限制任务数、不自动转入下游。保存后流水不可修改或删除。</p>
      <LoadErrorAlert :message="saveError" title="登记未完成" retry-text="重试保存" :loading="saving" @retry="save" />
      <ElFormItem><ElButton type="primary" native-type="submit" :loading="saving">保存{{ direction === 'receipt' ? '到料' : '出料' }}</ElButton></ElFormItem>
    </ElForm>
    <LoadErrorAlert :message="error" :loading="loading" @retry="load" />
    <ElTable v-if="!error" v-loading="loading" :data="rows" border empty-text="暂无到料或出料流水">
      <ElTableColumn label="类型" width="90"><template #default="{ row }">{{ row.direction === 'receipt' ? '到料' : '出料' }}</template></ElTableColumn>
      <ElTableColumn prop="quantity" label="数量" width="140" align="right" />
      <ElTableColumn prop="actor_username" label="操作人" min-width="110" />
      <ElTableColumn prop="created_at" label="时间" min-width="210" />
      <ElTableColumn prop="note" label="备注" min-width="180" />
    </ElTable>
    <ElPagination v-if="!error" v-model:current-page="page" layout="prev, pager, next, total" :total="total" :page-size="50" @current-change="load" />
    <template #footer><ElButton :disabled="saving" @click="visible = false">关闭</ElButton></template>
  </ElDialog>
</template>

<style scoped>
.movement-note { color: var(--erp-text-secondary); font-size: 13px; line-height: 1.6; }
.el-pagination { margin-top: 16px; justify-content: flex-end; }
</style>
