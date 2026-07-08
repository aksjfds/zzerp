<script setup lang="ts">
import type { AssemblyGroup } from '../composables/useAssemblyGroups'
defineProps<{ groups: AssemblyGroup[]; loading: boolean }>()
defineEmits<{ open: [group: AssemblyGroup] }>()
</script>
<template>
  <div v-loading="loading" class="assembly-groups">
    <article v-for="group in groups" :key="group.key" class="assembly-group-card">
      <strong>{{ group.productName }} · {{ group.name }}</strong>
      <ul>
        <li v-for="source in group.sources" :key="source.name">{{ source.name }}：可用 {{ source.available }} / 每件用量 {{
          source.required }}</li>
          <li>可装配 {{ group.capacity }}</li>
      </ul>
      <ElButton type="primary" :disabled="group.capacity < 1" @click="$emit('open', group)">开装配工单</ElButton>
    </article>
    <ElEmpty v-if="!loading && !groups.length" description="暂无可装配物料" :image-size="72" />
  </div>
</template>

<style scoped>
.assembly-groups {
  display: grid;
  gap: 12px;
  min-height: 150px;
}

.assembly-group-card {
  padding: 14px;
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #f8fafc;
}

.assembly-group-card p,
.assembly-group-card li {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.assembly-group-card ul {
  padding-left: 18px;
}
</style>
