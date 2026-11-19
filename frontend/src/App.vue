<script setup lang="ts">
import '@/styles/global.css'
import { useRoute } from 'vue-router'
import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import { zhCn } from 'element-plus/es/locales.mjs'
const route = useRoute()
</script>

<template>
  <ElConfigProvider :locale="zhCn" :dialog="{ alignCenter: true }">
    <WorkspaceLayout v-if="route.meta.requiresAuth"><RouterView /></WorkspaceLayout>
    <RouterView v-else />
  </ElConfigProvider>
</template>
