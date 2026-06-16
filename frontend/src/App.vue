<script setup lang="ts">
import '@/styles/global.css'
import { zhCn } from 'element-plus/es/locales.mjs'
</script>

<template>
  <ElConfigProvider :locale="zhCn">
    <RouterView />
  </ElConfigProvider>
</template>
