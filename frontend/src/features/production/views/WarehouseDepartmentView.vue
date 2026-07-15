<script setup lang="ts">
import ProductionDepartmentView from './ProductionDepartmentView.vue'
</script>

<template>
  <ProductionDepartmentView
    department-code="warehouse"
    department-name="仓库部门"
    description="外购配件需求、分批到货与入库流转。"
    mode="purchase"
  />
</template>
