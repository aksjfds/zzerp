<script setup lang="ts">
import { ref } from 'vue'
const element = ref<HTMLElement>()
defineExpose({ element })
defineProps<{
  title: string
  number?: string | null
  fields: [string, string | null, string?][]
  time?: string
  quality?: boolean
}>()
</script>
<template>
  <article ref="element" class="production-document-sheet">
    <header><h1>{{ title }}</h1><p>单据编号：{{ number || '未出料' }}</p></header>
    <table><tbody><tr v-for="[label, value, slotName] in fields" :key="label"><th>{{ label }}</th><td><slot :name="slotName || 'field'">{{ value || '—' }}</slot></td></tr></tbody></table>
    <p v-if="time" class="document-time">时间：{{ time }}</p>
    <footer v-if="!quality"><span>交出人：____________</span><span>接收人：____________</span></footer>
    <footer v-else><span>质检签字：____________</span><span>复核签字：____________</span></footer>
  </article>
</template>
<style scoped>
.production-document-sheet { color: #111; background: #fff; padding: 12px; font-family: Arial, 'Microsoft YaHei', sans-serif; }
header { text-align: center; margin-bottom: 20px; }
h1 { margin: 0 0 12px; font-size: 24px; }
header p { margin: 0; font-size: 13px; overflow-wrap: anywhere; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 14px; }
th, td { border: 1px solid #333; padding: 9px 12px; vertical-align: top; text-align: left; overflow-wrap: anywhere; white-space: pre-wrap; }
th { width: 110px; font-weight: 600; }
.document-time { margin: 16px 0 0; text-align: right; font-size: 13px; }
footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 24px; margin-top: 36px; font-size: 14px; break-inside: avoid; }
@media print { .production-document-sheet { padding: 0; } header { break-after: avoid; } }
</style>
