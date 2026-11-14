<script setup lang="ts">
import BomEditor from '../components/BomEditor.vue'
import ProcessFlowEditor from '../components/ProcessFlowEditor.vue'
import ProductBaseForm from '../components/ProductBaseForm.vue'
import ProductEditorHeader from '../components/ProductEditorHeader.vue'
import LoadErrorAlert from '@/shared/feedback/LoadErrorAlert.vue'
import { useProductEditor } from '../composables/useProductEditor'

const {
  form, baseFields, capabilities, baseDirty, bomDirty, flowDirty,
  activeAction, saving, productId, mode, canEdit, contentReady, baseReadOnly, appearanceReadOnly,
  appearances, requestedAppearance, flowSaveError, initializing, loadingProduct, initializationError,
  productError, initialize, retry, clearFlowSaveError, createProduct, saveBase, saveBom,
  saveFlow, saveFlowDraft, createAppearance, renameAppearance, switchAppearance, enterEdit, exitEdit, back, updateBom,
} = useProductEditor()
</script>

<template>
  <main class="editor-page">
    <ProductEditorHeader
      :product-id="productId" :name="contentReady ? form.product_name : ''" :mode="mode" :can-edit="canEdit"
      :selected-appearance="requestedAppearance ?? form.appearance_id ?? undefined"
      :appearances="appearances" :busy="saving"
      :loading="initializing || loadingProduct" :ready="contentReady" :action="activeAction"
      @back="back" @enter-edit="enterEdit" @exit-edit="exitEdit" @create-appearance="createAppearance"
      @rename-appearance="renameAppearance" @create-product="createProduct" @switch-appearance="switchAppearance"
    />
    <LoadErrorAlert :message="initializationError" :loading="initializing" @retry="initialize" />
    <LoadErrorAlert :message="productError" :loading="loadingProduct" @retry="retry" />
    <ElSkeleton v-if="productId && (initializing || loadingProduct)" :rows="6" animated />
    <template v-if="contentReady">
      <section class="editor-card">
        <div class="section-heading">
          <div><h2>产品基础信息</h2><p>产品级资料，所有外观共享；被生产计划引用后不可修改。</p></div>
          <ElButton v-if="productId && !baseReadOnly" type="primary" :disabled="!baseDirty || saving" :loading="activeAction === 'base'" @click="saveBase">保存基础信息</ElButton>
        </div>
        <ElAlert v-if="productId && !capabilities.baseEditable" title="产品已有生产计划引用，基础信息只读。" type="info" :closable="false" />
        <ElFormItem v-if="!productId" label="外观名称" required><ElInput v-model="form.appearance_name" :disabled="saving" maxlength="200" placeholder="如金色、银色" /></ElFormItem>
        <ProductBaseForm v-model="baseFields" :readonly="baseReadOnly" :disabled="saving" />
      </section>
      <section class="editor-card">
        <p>产品共用 BOM：修改会影响本产品全部外观。</p>
        <BomEditor :model-value="form.bom_items" :factory-code="form.factory_code" :readonly="appearanceReadOnly"
          :can-save="Boolean(productId && !appearanceReadOnly)" :dirty="bomDirty" :saving="saving"
          @update:model-value="updateBom" @save="saveBom" />
      </section>
      <section class="editor-card">
        <ElAlert v-if="!productId" title="请先保存产品基础信息和 BOM，再配置流程图" type="info" :closable="false" />
        <template v-else>
          <ElAlert v-if="mode === 'view'" title="查看模式为只读" type="info" :closable="false" />
          <ElAlert v-if="flowSaveError" :title="flowSaveError.message" type="error" :closable="false" show-icon />
          <ProcessFlowEditor ref="flowEditor" v-model="form.process_flow" :bom-items="form.bom_items"
            :readonly="appearanceReadOnly" @update:model-value="clearFlowSaveError">
            <template v-if="!appearanceReadOnly" #actions="{ disabled }">
              <ElButton plain :disabled="disabled || !flowDirty || saving" :loading="activeAction === 'flow-draft'" @click="saveFlowDraft">保存草稿</ElButton>
              <ElButton type="primary" :disabled="disabled || (!flowDirty && !form.process_flow_is_draft) || saving"
                :loading="activeAction === 'flow'" @click="saveFlow">确认并保存流程</ElButton>
            </template>
          </ProcessFlowEditor>
        </template>
      </section>
    </template>
  </main>
</template>

<style scoped>
.editor-page { min-height: 100vh; padding: var(--erp-page-gutter); background: var(--erp-bg); }
.editor-card { margin-bottom: 20px; padding: 24px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius-lg); background: var(--erp-surface); }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; margin-bottom: 20px; }
h2 { margin: 0 0 6px; font-size: 18px; }
p { margin: 0; color: var(--erp-text-secondary); font-size: 13px; }
.el-alert { margin-bottom: 16px; }
@media (max-width: 640px) { .editor-card { padding: 16px; } .section-heading { flex-wrap: wrap; } }
</style>
