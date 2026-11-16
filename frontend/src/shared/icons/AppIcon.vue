<script setup lang="ts">
defineProps<{ name: 'products' | 'plans' | 'progress' | 'logout' | 'arrow' }>()
const paths = {
  products: 'm12 3 9 5-9 5-9-5 9-5Zm-9 5v9l9 5 9-5V8M12 13v9',
  plans: 'M8 4H5v17h14V4h-3M8 3h8v4H8V3Zm0 9h8m-8 4h5',
  progress: 'M4 20V10m8 10V4m8 16v-7M2 21h20',
  logout: 'M9 4H4v16h5m5-13 5 5-5 5m-5-5h14',
  arrow: 'm9 5 7 7-7 7',
} as const
</script>

<template>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name]" /></svg>
</template>

<style scoped>
svg { display: block; width: 20px; height: 20px; flex-shrink: 0; }
</style>
