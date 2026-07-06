<script setup lang="ts">
import type { BomItem } from '../domain/types'

const props = defineProps<{ modelValue: BomItem[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: BomItem[]] }>()

function update(index: number, field: keyof BomItem, value: string | number | undefined) {
  const rows = props.modelValue.map((item) => ({ ...item }))
  const row = rows[index]
  if (!row) return
  Object.assign(row, { [field]: field === 'pcs' ? (value ?? 1) : value })
  emit('update:modelValue', rows)
}

function addRow() {
  emit('update:modelValue', [
    ...props.modelValue,
    { part_name: '', part_no: '', pcs: 1, remark: '' },
  ])
}

function removeRow(index: number) {
  emit('update:modelValue', props.modelValue.filter((_, itemIndex) => itemIndex !== index))
}

function fieldError(index: number, field: 'part_name' | 'part_no' | 'pcs') {
  const item = props.modelValue[index]
  if (!item) return '必填'
  if (field === 'pcs') return item.pcs > 0 ? '' : '必须大于 0'
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
        <p>配件名称、配件编号和用量必填；保存后可拖入流程图。</p>
      </div>
      <ElButton type="primary" plain @click="addRow">新增 BOM 行</ElButton>
    </div>
    <ElTable :data="modelValue" border empty-text="请新增至少一条 BOM 明细">
      <ElTableColumn type="index" label="#" width="54" />
      <ElTableColumn label="配件名称" min-width="170">
        <template #default="{ row, $index }">
          <ElFormItem :error="fieldError($index, 'part_name')">
            <ElInput
              :model-value="row.part_name"
              placeholder="例如：主体"
              @update:model-value="update($index, 'part_name', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="配件编号" min-width="170">
        <template #default="{ row, $index }">
          <ElFormItem :error="fieldError($index, 'part_no')">
            <ElInput
              :model-value="row.part_no"
              placeholder="例如：Z8412-01"
              @update:model-value="update($index, 'part_no', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="用量" width="140">
        <template #default="{ row, $index }">
          <ElFormItem :error="fieldError($index, 'pcs')">
            <ElInputNumber
              :model-value="row.pcs"
              :min="1"
              :step="1"
              :precision="0"
              controls-position="right"
              @update:model-value="update($index, 'pcs', $event)"
            />
          </ElFormItem>
        </template>
      </ElTableColumn>
      <ElTableColumn label="备注" min-width="180">
        <template #default="{ row, $index }">
          <ElInput
            :model-value="row.remark"
            placeholder="可为空"
            @update:model-value="update($index, 'remark', $event)"
          />
        </template>
      </ElTableColumn>
      <ElTableColumn label="操作" width="84" fixed="right">
        <template #default="{ $index }">
          <ElButton type="danger" link @click="removeRow($index)">删除</ElButton>
        </template>
      </ElTableColumn>
    </ElTable>
  </section>
</template>

<style scoped>
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
h2 { margin: 0 0 5px; font-size: 18px; }
p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.bom-editor :deep(.el-form-item) { margin-bottom: 14px; }
</style>
