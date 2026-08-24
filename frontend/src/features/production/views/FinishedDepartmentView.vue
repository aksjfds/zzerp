<script setup lang="ts">
import { InventoryDepartmentView } from '@/features/inventory'
</script>

<template>
  <InventoryDepartmentView
    department-code="finished"
    title="成品部"
    show-order-finished-operations
  />
</template>
