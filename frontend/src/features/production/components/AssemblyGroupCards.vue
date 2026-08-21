<script setup lang="ts">
import type { AssemblyGroup } from '../composables/useAssemblyGroups'
import { repositoryStatusClass, repositoryStatusLabel } from '../domain/repositoryWorkStatus'
withDefaults(defineProps<{
  groups: AssemblyGroup[]
  loading: boolean
  selectedKey?: string | null
  showEmpty?: boolean
}>(), { showEmpty: true })
defineEmits<{ open: [group: AssemblyGroup]; select: [group: AssemblyGroup] }>()
</script>
<template>
  <div v-loading="loading" class="assembly-groups">
    <article v-for="group in groups" :key="group.key" class="assembly-group-card" :class="{ selected: group.key === selectedKey }" tabindex="0" @click="$emit('select', group)" @keydown.enter="$emit('select', group)">
      <div class="heading"><strong>{{ group.productName }} · {{ group.name }}</strong><ElTag class="repository-status-tag" :class="group.kind === 'history' ? repositoryStatusClass('completed') : group.kind === 'current' && !group.complete ? repositoryStatusClass('unprocessed') : repositoryStatusClass(group.status)" effect="plain" size="small">{{ group.kind === 'history' ? '历史' : group.kind === 'current' && !group.complete ? '等待物料' : repositoryStatusLabel(group.status, 'assembly') }}</ElTag></div>
      <p>到达时间：{{ group.arrivedAt || '-' }}</p>
      <ul v-if="group.kind === 'current'">
        <li v-for="source in group.sources" :key="source.name">{{ source.name }}：可用 {{ source.available }} / 每件用量 {{
          source.required }}</li>
          <li>可开工 {{ group.capacity }}</li>
          <li v-if="!group.complete">物料尚未到齐</li>
      </ul>
      <ElButton v-if="group.kind === 'current'" type="primary" :disabled="!group.complete || group.capacity < 1" @click.stop="$emit('open', group)">开{{ group.workshopName }}工单</ElButton>
    </article>
    <ElEmpty v-if="showEmpty && !loading && !groups.length" description="暂无可装配物料" :image-size="72" />
  </div>
</template>

<style scoped>
.assembly-groups {
  display: grid;
  grid-auto-rows: max-content;
  align-content: start;
  gap: 12px;
  min-height: 150px;
}

.assembly-group-card {
  padding: 14px;
  border: 1px solid transparent;
  border-radius: var(--erp-radius);
  background: var(--md-surface-container-low);
  cursor: pointer;
  transition: border-color .15s, box-shadow .15s;
}
.assembly-group-card:hover, .assembly-group-card:focus-visible { border-color: var(--erp-primary); background: var(--md-surface-container); outline: none; }
.assembly-group-card.selected { border-color: var(--md-primary); background: var(--md-primary-container); box-shadow: none; }
.heading { display: flex; justify-content: space-between; gap: 12px; }

.assembly-group-card p,
.assembly-group-card li {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.assembly-group-card ul {
  padding-left: 18px;
}
@media (max-width: 480px) { .heading { align-items: flex-start; flex-direction: column; } }
</style>
