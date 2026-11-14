<script setup lang="ts">
import { useCompactViewport } from '@/shared/layout/useCompactViewport'

import { watch } from 'vue'
import { nextPartNumber } from '../domain/bomNumbers'
import type { BomItem } from '../domain/types'

const compact = useCompactViewport()
const props = defineProps<{
  modelValue: BomItem[]
  factoryCode: string
  readonly?: boolean
  canSave?: boolean
  dirty?: boolean
  saving?: boolean
}>()
const emit = defineEmits<{
  'update:modelValue': [value: BomItem[]]
  save: []
}>()
const generatedNumbers = new Set<string>()

function update(index: number, field: keyof BomItem, value: string | number | undefined) {
  if (props.readonly) return
  const rows = props.modelValue.map((item) => ({ ...item }))
  const row = rows[index]
  if (!row) return
  if (field === 'part_no') generatedNumbers.delete(row.part_no)
  Object.assign(row, { [field]: field === 'pcs' ? (value ?? 1) : value })
  emit('update:modelValue', rows)
}

function addRow() {
  if (props.readonly) return
  const partNo = nextPartNumber(props.factoryCode, props.modelValue)
  if (partNo) generatedNumbers.add(partNo)
  emit('update:modelValue', [
    ...props.modelValue,
    { part_name: '', part_no: partNo, pcs: 1, remark: '' },
  ])
}

function removeRow(index: number) {
  if (props.readonly) return
  emit('update:modelValue', props.modelValue.filter((_, itemIndex) => itemIndex !== index))
}

watch(() => props.factoryCode, () => {
  if (props.readonly || !props.factoryCode.trim()) return
  const rows = props.modelValue.map(item => ({ ...item }))
  const automatic = rows.filter(row => row.id === undefined
    && (!row.part_no.trim() || generatedNumbers.has(row.part_no)))
  for (const row of automatic) row.part_no = ''
  for (const row of automatic) {
    row.part_no = nextPartNumber(props.factoryCode, rows)
    generatedNumbers.add(row.part_no)
  }
  if (automatic.length) emit('update:modelValue', rows)
}, { immediate: true })

function fieldError(index: number, field: 'part_name' | 'part_no' | 'pcs') {
  const item = props.modelValue[index]
  if (!item) return '必填'
  if (field === 'pcs') return Number.isInteger(item.pcs) && item.pcs > 0 && item.pcs <= 2147483647
    ? '' : '请输入有效的正整数用量'
  if (!item[field].trim()) return '必填'
  if (
    field === 'part_no'
    && props.modelValue.some((row, rowIndex) =>
      rowIndex !== index && row.part_no.trim() === item.part_no.trim(),
    )
  ) return '配件编号重复'
  return ''
}
</script>

<template>
  <section class="bom-editor">
    <div class="section-heading">
      <div>
        <h2>BOM 明细</h2>
        <p>{{ readonly ? '当前产品外观的配件、用量与备注。' : '配件名称、配件编号和用量必填；保存后可拖入流程图。' }}</p>
      </div>
      <div v-if="!readonly" class="heading-actions">
        <ElButton plain :disabled="saving" @click="addRow">新增配件</ElButton>
        <ElButton
          v-if="canSave"
          type="primary"
          :disabled="!dirty"
          :loading="saving"
          @click="emit('save')"
        >保存 BOM</ElButton>
      </div>
    </div>
    <ElTable v-table-column-widths="'engineering.bom-editor'" :data="modelValue" border table-layout="auto" :empty-text="readonly ? '当前外观暂无 BOM 明细' : '请新增至少一条 BOM 明细'">
      <ElTableColumn type="index" label="#" width="54" />
      <ElTableColumn label="配件名称" min-width="170">
        <template #default="{ row, $index }">
          <span v-if="readonly" class="readonly-value">{{ row.part_name }}</span>
          <ElFormItem v-else :error="fieldError($index, 'part_name')">
            <ElInput
              :model-value="row.part_name"
              :disabled="readonly"
              placeholder="例如：主体"
              :aria-label="`第 ${$index + 1} 行配件名称`"
              @update:model-value="update($index, 'part_name', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="配件编号" min-width="170">
        <template #default="{ row, $index }">
          <span v-if="readonly" class="readonly-value">{{ row.part_no }}</span>
          <ElFormItem v-else :error="fieldError($index, 'part_no')">
            <ElInput
              :model-value="row.part_no"
              :disabled="readonly"
              placeholder="例如：Z8412-01"
              :aria-label="`第 ${$index + 1} 行配件编号`"
              @update:model-value="update($index, 'part_no', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="用量" width="140" align="right">
        <template #default="{ row, $index }">
          <span v-if="readonly" class="readonly-value numeric">{{ row.pcs }}</span>
          <ElFormItem v-else :error="fieldError($index, 'pcs')">
            <ElInputNumber
              :model-value="row.pcs"
              :disabled="readonly"
              :min="1"
              :max="2147483647"
              :step="1"
              :precision="0"
              controls-position="right"
              :aria-label="`第 ${$index + 1} 行用量`"
              @update:model-value="update($index, 'pcs', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="备注" min-width="180">
        <template #default="{ row, $index }">
          <span v-if="readonly" class="readonly-value">{{ row.remark || '—' }}</span>
          <ElInput
            v-else
            :model-value="row.remark"
            :disabled="readonly"
            placeholder="可为空"
            :aria-label="`第 ${$index + 1} 行备注`"
            @update:model-value="update($index, 'remark', $event)"
          />
        </template>
      </ElTableColumn>
      <ElTableColumn v-if="!readonly" label="操作" width="84" :fixed="compact ? false : 'right'">
        <template #default="{ $index }">
          <ElPopconfirm title="确定删除这条 BOM 配件吗？" @confirm="removeRow($index)">
            <template #reference><ElButton type="danger" link>删除</ElButton></template>
          </ElPopconfirm>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
.heading-actions { display: flex; align-items: center; flex: none; gap: 8px; }
.heading-actions :deep(.el-button + .el-button) { margin-left: 0; }
h2 { margin: 0 0 5px; font-size: 18px; }
p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.bom-editor :deep(.el-form-item) { margin-bottom: 14px; }
.bom-editor :deep(.el-input-number) { width: 100%; }
.readonly-value { color: var(--erp-text); overflow-wrap: anywhere; }
.numeric { font-variant-numeric: tabular-nums; }
@media (max-width: 600px) {
  .section-heading { align-items: flex-start; flex-direction: column; gap: 10px; }
  .heading-actions { display: grid; width: 100%; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .heading-actions :deep(.el-button) { width: 100%; margin: 0; }
}
</style>
