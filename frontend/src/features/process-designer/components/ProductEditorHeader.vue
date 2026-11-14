<script setup lang="ts">
defineProps<{
  productId: number | null; name: string; mode: 'view' | 'edit'; canEdit: boolean;
  selectedAppearance?: number; appearances: { id: number; appearance_name: string }[];
  busy: boolean; loading: boolean; ready: boolean; action: string | null;
}>()
const emit = defineEmits<{
  back: []; enterEdit: []; exitEdit: []; createAppearance: []; renameAppearance: []; createProduct: []; switchAppearance: [value: number];
}>()
</script>

<template>
  <header class="editor-header">
    <div>
      <div class="page-kicker">工程管理 / {{ productId ? mode === 'view' ? '查看产品' : '编辑产品' : '录入产品' }}</div>
      <h1>{{ productId ? name || '产品工程资料' : '录入新产品' }}</h1>
    </div>
    <div class="editor-actions">
      <div v-if="productId" class="appearance_id-selector">
        <span>查看外观</span>
        <ElSelect :model-value="selectedAppearance" :disabled="busy || loading" :loading="loading" @change="emit('switchAppearance', $event)">
          <ElOption v-for="appearance_id in appearances" :key="appearance_id.id" :label="appearance_id.appearance_name" :value="appearance_id.id" />
        </ElSelect>

      </div>
      <ElButton :disabled="busy" @click="emit('back')">返回产品列表</ElButton>
      <ElButton v-if="productId && mode === 'view' && canEdit" type="primary" :disabled="!ready" @click="emit('enterEdit')">进入编辑</ElButton>
      <ElButton v-if="productId && mode === 'edit'" :disabled="busy || !ready" @click="emit('exitEdit')">退出编辑</ElButton>
      <ElButton v-if="productId && mode === 'edit' && canEdit" type="primary" plain :disabled="busy || !ready" :loading="action === 'appearance-create'" @click="emit('createAppearance')">新增外观</ElButton>
      <ElButton v-if="productId && mode === 'edit' && canEdit" :disabled="busy || !ready" @click="emit('renameAppearance')">重命名外观</ElButton>
      <ElButton v-if="!productId && canEdit" type="primary" :disabled="busy || !ready" :loading="action === 'create'" @click="emit('createProduct')">保存产品并配置流程</ElButton>
    </div>
  </header>
</template>

<style scoped>
.editor-header { display: flex; justify-content: space-between; align-items: center; gap: 24px; margin-bottom: 20px; }
.page-kicker { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
h1 { margin: 6px 0 0; font-size: 24px; }
.editor-actions, .appearance_id-selector { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.appearance_id-selector { color: var(--erp-text-secondary); font-size: 13px; }
.appearance_id-selector .el-select { width: 110px; }
.editor-actions :deep(.el-button + .el-button) { margin-left: 0; }
@media (max-width: 900px) { .editor-header { align-items: flex-start; flex-direction: column; } }
</style>
