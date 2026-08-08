<script setup lang="ts">
import ProductionDepartmentView from './ProductionDepartmentView.vue'
</script>

<template>
  <ProductionDepartmentView
    department-code="purchasing"
    department-name="采购部"
    description="管理生产流程中的外购物料、外购单及到货处理。"
    mode="purchase"
  />
</template>
