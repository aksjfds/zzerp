<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  cancelV2CustomerOrder,
  confirmV2CustomerOrder,
  createV2CustomerOrder,
  createV2CustomerOrderChange,
  queryV2CustomerOrders,
  updateV2CustomerOrder,
} from '@/api/customerOrders'
import { queryV2Products, queryV2SurfaceTreatments } from '@/api/engineering'
import type { EngineeringProduct, SurfaceTreatmentSummary } from '@/types/engineering'
import type {
  CustomerOrder,
  CustomerOrderCreateInput,
  CustomerOrderStatus,
} from '@/types/sales'

type OrderFormRow = {
  productId?: number
  productCustomerCodeId?: number
  treatmentId?: number
  quantity: number
  deliveryDate: string
}

const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()
const keyword = ref('')
const statusFilter = ref<CustomerOrderStatus>()
const orders = ref<CustomerOrder[]>([])
const products = ref<EngineeringProduct[]>([])
const treatments = ref<SurfaceTreatmentSummary[]>([])
const dialogVisible = ref(false)
const editingOrderId = ref<number>()
const form = reactive({
  customerName: '',
  purchaseOrderNo: '',
  orderDate: '',
  note: '',
  items: [] as OrderFormRow[],
})

const statusLabels: Record<CustomerOrderStatus, string> = {
  draft: '草稿',
  confirmed: '已确认',
  planned: '已排产',
  completed: '已完成',
  cancelled: '已取消',
  superseded: '已取代',
}
const customerOptions = computed(() => [...new Set(
  products.value.filter((product) => product.status === 'published')
    .flatMap((product) => product.customerCodes)
    .filter((item) => item.active)
    .map((item) => item.customerName),
)].sort())
const availableProducts = computed(() => products.value.filter((product) => (
  product.status === 'published' && product.customerCodes.some(
    (item) => item.active && item.customerName === form.customerName,
  )
)))

function codeOptions(row: OrderFormRow) {
  return products.value.find((item) => item.id === row.productId)?.customerCodes.filter(
    (item) => item.active && item.customerName === form.customerName,
  ) ?? []
}

function treatmentOptions(row: OrderFormRow) {
  const code = codeOptions(row).find((item) => item.id === row.productCustomerCodeId)
  return treatments.value.filter((item) => code?.treatmentIds.includes(item.id) && item.active)
}

function addItem() {
  form.items.push({ quantity: 1, deliveryDate: '' })
}

function localToday() {
  const today = new Date()
  const month = String(today.getMonth() + 1).padStart(2, '0')
  const day = String(today.getDate()).padStart(2, '0')
  return `${today.getFullYear()}-${month}-${day}`
}

function changeCustomer() {
  form.items = []
  addItem()
}

function changeProduct(row: OrderFormRow) {
  const codes = codeOptions(row)
  row.productCustomerCodeId = codes.length === 1 ? codes[0].id : undefined
  row.treatmentId = undefined
}

function changeCustomerCode(row: OrderFormRow) {
  row.treatmentId = undefined
}

async function loadOrders() {
  loading.value = true
  try {
    orders.value = await queryV2CustomerOrders({
      keyword: keyword.value.trim() || undefined,
      status: statusFilter.value,
    })
  } catch {
    ElMessage.error('客户订单加载失败')
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  editingOrderId.value = undefined
  form.customerName = ''
  form.purchaseOrderNo = ''
  form.orderDate = localToday()
  form.note = ''
  form.items = []
  addItem()
  dialogVisible.value = true
}

function openEditDialog(order: CustomerOrder) {
  editingOrderId.value = order.id
  form.customerName = order.customerName
  form.purchaseOrderNo = order.purchaseOrderNo
  form.orderDate = order.orderDate
  form.note = order.note ?? ''
  form.items = order.items.map((item) => ({
    productId: item.productId,
    productCustomerCodeId: item.productCustomerCodeId,
    treatmentId: item.treatmentId ?? undefined,
    quantity: item.quantity,
    deliveryDate: item.deliveryDate,
  }))
  dialogVisible.value = true
}

async function saveOrder() {
  if (
    !form.customerName.trim()
    || !form.purchaseOrderNo.trim()
    || !form.orderDate
    || !form.items.length
    || form.items.some((item) => (
      !item.productCustomerCodeId || !item.deliveryDate || item.quantity < 1
    ))
  ) {
    ElMessage.warning('请完整填写订单和产品明细')
    return
  }
  const items = form.items.map((item) => ({
    productCustomerCodeId: item.productCustomerCodeId as number,
    treatmentId: item.treatmentId,
    quantity: item.quantity,
    deliveryDate: item.deliveryDate,
  }))
  try {
    if (editingOrderId.value) {
      await updateV2CustomerOrder(editingOrderId.value, {
        orderDate: form.orderDate,
        note: form.note,
        items,
      })
    } else {
      const payload: CustomerOrderCreateInput = {
        customerName: form.customerName,
        purchaseOrderNo: form.purchaseOrderNo,
        orderDate: form.orderDate,
        note: form.note,
        items,
      }
      await createV2CustomerOrder(payload)
    }
    dialogVisible.value = false
    await loadOrders()
    ElMessage.success('客户订单草稿已保存')
  } catch {
    ElMessage.error('客户订单保存失败，请检查订单号和产品明细')
  }
}

async function executeAction(
  order: CustomerOrder,
  action: 'confirm' | 'change' | 'cancel',
) {
  const messages = {
    confirm: '确认后订单不能直接修改，确定继续？',
    change: '确定基于该订单创建新版本草稿？',
    cancel: '确定取消该客户订单？',
  }
  try {
    await ElMessageBox.confirm(messages[action], '客户订单')
    if (action === 'confirm') await confirmV2CustomerOrder(order.id)
    else if (action === 'change') await createV2CustomerOrderChange(order.id)
    else await cancelV2CustomerOrder(order.id)
    await loadOrders()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error('订单操作失败')
  }
}

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(async () => {
  try {
    ;[products.value, treatments.value] = await Promise.all([
      queryV2Products(),
      queryV2SurfaceTreatments(),
    ])
  } catch {
    ElMessage.error('产品基础资料加载失败')
  }
  await loadOrders()
})
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div><span>业务部</span><h1>客户订单</h1></div>
      <div class="header-actions">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElInput v-model="keyword" clearable placeholder="客户或采购订单号" />
        <ElSelect v-model="statusFilter" clearable placeholder="全部状态">
          <ElOption
            v-for="(label, value) in statusLabels"
            :key="value"
            :label="label"
            :value="value"
          />
        </ElSelect>
        <ElButton @click="loadOrders">查询</ElButton>
        <ElButton type="primary" @click="openCreateDialog">新增客户订单</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </div>
    </header>

    <section v-loading="loading" class="content-card">
      <ElTable :data="orders" stripe>
        <ElTableColumn prop="customerName" label="客户" width="130" />
        <ElTableColumn prop="purchaseOrderNo" label="采购订单号" width="170" />
        <ElTableColumn prop="versionNo" label="版本" width="70" />
        <ElTableColumn prop="orderDate" label="订单日期" width="120" />
        <ElTableColumn label="产品明细" min-width="420">
          <template #default="{ row }">
            <div v-for="item in row.items" :key="item.id" class="item-summary">
              {{ item.factoryCode }} · {{ item.customerProductCode }} ·
              {{ item.treatmentName || '无表面处理' }} · {{ item.quantity }} pcs ·
              {{ item.deliveryDate }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="100">
          <template #default="{ row }">{{ statusLabels[row.status] }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'draft'">
              <ElButton text @click="openEditDialog(row)">编辑</ElButton>
              <ElButton text type="primary" @click="executeAction(row, 'confirm')">确认</ElButton>
              <ElButton text type="danger" @click="executeAction(row, 'cancel')">取消</ElButton>
            </template>
            <template v-else-if="row.status === 'confirmed'">
              <ElButton text @click="executeAction(row, 'change')">创建变更</ElButton>
              <ElButton text type="danger" @click="executeAction(row, 'cancel')">取消</ElButton>
            </template>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>

    <ElDialog
      v-model="dialogVisible"
      :title="editingOrderId ? '编辑客户订单草稿' : '新增客户订单'"
      width="1040px"
    >
      <ElForm label-position="top">
        <div class="order-fields">
          <ElFormItem label="客户">
            <ElSelect
              v-model="form.customerName"
              :disabled="Boolean(editingOrderId)"
              filterable
              @change="changeCustomer"
            >
              <ElOption v-for="item in customerOptions" :key="item" :label="item" :value="item" />
            </ElSelect>
          </ElFormItem>
          <ElFormItem label="采购订单号">
            <ElInput v-model="form.purchaseOrderNo" :disabled="Boolean(editingOrderId)" />
          </ElFormItem>
          <ElFormItem label="订单日期">
            <ElDatePicker v-model="form.orderDate" value-format="YYYY-MM-DD" />
          </ElFormItem>
        </div>
        <ElFormItem label="备注"><ElInput v-model="form.note" /></ElFormItem>
      </ElForm>
      <ElDivider content-position="left">订单产品</ElDivider>
      <div v-for="(item, index) in form.items" :key="index" class="order-row">
        <ElSelect
          v-model="item.productId"
          filterable
          placeholder="产品"
          @change="changeProduct(item)"
        >
          <ElOption
            v-for="product in availableProducts"
            :key="product.id"
            :label="`${product.factoryCode} · ${product.productName}`"
            :value="product.id"
          />
        </ElSelect>
        <ElSelect
          v-model="item.productCustomerCodeId"
          placeholder="客编"
          @change="changeCustomerCode(item)"
        >
          <ElOption
            v-for="code in codeOptions(item)"
            :key="code.id"
            :label="code.customerProductCode"
            :value="code.id"
          />
        </ElSelect>
        <ElSelect v-model="item.treatmentId" clearable placeholder="无表面处理">
          <ElOption
            v-for="treatment in treatmentOptions(item)"
            :key="treatment.id"
            :label="treatment.treatmentName"
            :value="treatment.id"
          />
        </ElSelect>
        <ElInputNumber v-model="item.quantity" :min="1" />
        <ElDatePicker
          v-model="item.deliveryDate"
          value-format="YYYY-MM-DD"
          placeholder="交货日期"
        />
        <ElButton type="danger" text @click="form.items.splice(index, 1)">删除</ElButton>
      </div>
      <ElButton @click="addItem">添加产品</ElButton>
      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="saveOrder">保存草稿</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 22px; background: var(--erp-bg); }
.page-header, .content-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
  padding: 16px 20px;
}
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 6px 0 0; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.header-actions :deep(.el-input) { width: 220px; }
.header-actions :deep(.el-select) { width: 140px; }
.content-card { padding: 18px; }
.item-summary + .item-summary { margin-top: 5px; }
.order-fields { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.order-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 120px 160px auto;
  gap: 8px;
  margin-bottom: 10px;
}
@media (max-width: 1000px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .header-actions, .order-fields, .order-row {
    display: grid;
    grid-template-columns: 1fr;
    width: 100%;
  }
}
</style>
