<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  addV2Material,
  addV2ProductCustomerCode,
  createV2Product,
  deactivateV2Product,
  publishV2Product,
  queryV2Products,
  queryV2SurfaceTreatments,
  updateV2Material,
  updateV2ProductName,
  updateV2ProductCustomerCode,
} from '@/api/engineering'
import type {
  EngineeringProduct,
  MaterialInput,
  MaterialSummary,
  MaterialType,
  ProductCustomerCodeInput,
  ProductCustomerCodeDetail,
  ProductInput,
  SurfaceTreatmentSummary,
} from '@/types/engineering'

const loading = ref(false)
const router = useRouter()
const authStore = useAuthStore()
const keyword = ref('')
const products = ref<EngineeringProduct[]>([])
const treatments = ref<SurfaceTreatmentSummary[]>([])
const activeProduct = ref<EngineeringProduct | null>(null)
const productDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const customerDialogVisible = ref(false)
const materialDialogVisible = ref(false)
const editingCustomerCodeId = ref<number>()
const editingMaterialId = ref<number>()

const productForm = reactive<ProductInput>({
  factoryCode: '',
  productName: '',
  customerCodes: [],
  materials: [],
})
const customerForm = reactive<ProductCustomerCodeInput>({
  customerName: '',
  customerProductCode: '',
  treatmentIds: [],
})
const materialForm = reactive<MaterialInput>({
  materialCode: '',
  materialName: '',
  materialType: 'self_made',
  materialGrade: '',
  specification: '',
  note: '',
})

const materialTypeLabels: Record<MaterialType, string> = {
  finished: '成品',
  semi_finished: '半成品',
  self_made: '自制配件',
  purchased: '外购配件',
}
const productStatusLabels = {
  draft: '草稿',
  published: '已发布',
  inactive: '已停用',
} as const

function treatmentOptions(customerName: string) {
  return treatments.value.filter(
    (item) => item.active && item.customerName === customerName.trim(),
  )
}

function addCustomerRow() {
  productForm.customerCodes.push({
    customerName: '',
    customerProductCode: '',
    treatmentIds: [],
  })
}

function addMaterialRow() {
  productForm.materials.push({
    materialCode: '',
    materialName: '',
    materialType: 'self_made',
    materialGrade: '',
    specification: '',
    note: '',
  })
  refreshProductMaterialCodes()
}

function refreshProductMaterialCodes() {
  const factoryCode = productForm.factoryCode.trim()
  let sequence = 1
  for (const material of productForm.materials) {
    if (material.materialType === 'semi_finished') {
      material.materialCode = ''
      continue
    }
    material.materialCode = factoryCode
      ? `${factoryCode}-${String(sequence).padStart(2, '0')}`
      : ''
    sequence += 1
  }
}

function changeNewMaterialType() {
  refreshProductMaterialCodes()
}

function removeNewMaterial(index: number) {
  productForm.materials.splice(index, 1)
  refreshProductMaterialCodes()
}

function nextPartCode(product: EngineeringProduct) {
  const prefix = `${product.factoryCode}-`
  const used = new Set(
    product.materials.flatMap((item) => {
      if (!item.materialCode.startsWith(prefix)) return []
      const suffix = item.materialCode.slice(prefix.length)
      return /^\d+$/.test(suffix) ? [Number(suffix)] : []
    }),
  )
  let sequence = 1
  while (used.has(sequence)) sequence += 1
  return `${prefix}${String(sequence).padStart(2, '0')}`
}

function resetProductForm() {
  productForm.factoryCode = ''
  productForm.productName = ''
  productForm.customerCodes = []
  productForm.materials = []
  addCustomerRow()
  addMaterialRow()
}

function openProductDialog() {
  resetProductForm()
  productDialogVisible.value = true
}

function productFormValid() {
  return Boolean(
    productForm.factoryCode.trim()
    && productForm.productName.trim()
    && productForm.customerCodes.length
    && productForm.customerCodes.every(
      (item) => item.customerName.trim() && item.customerProductCode.trim(),
    )
    && productForm.materials.every(
      (item) =>
        item.materialName.trim()
        && (item.materialType === 'semi_finished' || item.materialCode?.trim()),
    ),
  )
}

async function loadProducts() {
  loading.value = true
  try {
    products.value = await queryV2Products(keyword.value.trim() || undefined)
  } catch {
    ElMessage.error('产品资料加载失败')
  } finally {
    loading.value = false
  }
}

function syncActiveProduct() {
  if (!activeProduct.value) return
  activeProduct.value = products.value.find(
    (item) => item.id === activeProduct.value?.id,
  ) ?? null
}

async function submitProduct() {
  if (!productFormValid()) {
    ElMessage.warning('请完整填写产品、客户客编和物料资料')
    return
  }
  try {
    await createV2Product(productForm)
    productDialogVisible.value = false
    await loadProducts()
    ElMessage.success('产品已建立，成品物料已自动生成')
  } catch {
    ElMessage.error('产品创建失败，请检查厂编、客编和配件编号')
  }
}

function openDetail(product: EngineeringProduct) {
  activeProduct.value = product
  detailDrawerVisible.value = true
}

async function editProductName(product: EngineeringProduct) {
  try {
    const result = await ElMessageBox.prompt('请输入产品名称', '编辑产品', {
      inputValue: product.productName,
      inputValidator: (value) => Boolean(value.trim()) || '产品名称不能为空',
    })
    await updateV2ProductName(product.id, result.value)
    await loadProducts()
    syncActiveProduct()
    ElMessage.success('产品名称已更新')
  } catch {
    return
  }
}

async function publishProduct(product: EngineeringProduct) {
  try {
    await ElMessageBox.confirm(
      '发布后产品名称和物料主档将锁定，'
        + '后续BOM、半成品组成和路线通过版本维护。确认发布？',
      '发布产品',
      { type: 'warning', confirmButtonText: '确认发布' },
    )
    await publishV2Product(product.id)
    await loadProducts()
    syncActiveProduct()
    ElMessage.success('产品已发布，可以用于客户订单')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    const detail = axios.isAxiosError(error)
      ? error.response?.data?.detail
      : undefined
    ElMessage.error(
      typeof detail === 'string'
        ? detail
        : '发布失败，请确认BOM、半成品组成和工艺路线均已发布',
    )
  }
}

async function deactivateProduct(product: EngineeringProduct) {
  try {
    await ElMessageBox.confirm(
      '停用后不能再用于新客户订单，且不能恢复。确认停用？',
      '停用产品',
      { type: 'warning', confirmButtonText: '确认停用' },
    )
    await deactivateV2Product(product.id)
    await loadProducts()
    syncActiveProduct()
    ElMessage.success('产品已停用')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error('产品停用失败')
  }
}

function openCustomerDialog(product: EngineeringProduct) {
  activeProduct.value = product
  editingCustomerCodeId.value = undefined
  customerForm.customerName = ''
  customerForm.customerProductCode = ''
  customerForm.treatmentIds = []
  customerDialogVisible.value = true
}

function editCustomerCode(
  product: EngineeringProduct | null,
  item: ProductCustomerCodeDetail,
) {
  if (!product) return
  activeProduct.value = product
  editingCustomerCodeId.value = item.id
  customerForm.customerName = item.customerName
  customerForm.customerProductCode = item.customerProductCode
  customerForm.treatmentIds = [...item.treatmentIds]
  customerDialogVisible.value = true
}

async function submitCustomerCode() {
  if (!activeProduct.value) return
  try {
    if (editingCustomerCodeId.value) {
      activeProduct.value = await updateV2ProductCustomerCode(editingCustomerCodeId.value, {
        treatmentIds: customerForm.treatmentIds,
      })
    } else {
      activeProduct.value = await addV2ProductCustomerCode(
        activeProduct.value.id,
        customerForm,
      )
    }
    customerDialogVisible.value = false
    await loadProducts()
    syncActiveProduct()
    ElMessage.success('客户客编已添加')
  } catch {
    ElMessage.error('客户客编添加失败')
  }
}

function openMaterialDialog(product: EngineeringProduct) {
  activeProduct.value = product
  editingMaterialId.value = undefined
  materialForm.materialCode = nextPartCode(product)
  materialForm.materialName = ''
  materialForm.materialType = 'self_made'
  materialForm.materialGrade = ''
  materialForm.specification = ''
  materialForm.note = ''
  materialDialogVisible.value = true
}

function changeMaterialDialogType() {
  if (editingMaterialId.value || !activeProduct.value) return
  materialForm.materialCode = materialForm.materialType === 'semi_finished'
    ? ''
    : nextPartCode(activeProduct.value)
}

function editMaterial(product: EngineeringProduct | null, item: MaterialSummary) {
  if (!product) return
  activeProduct.value = product
  editingMaterialId.value = item.id
  materialForm.materialCode = item.materialCode
  materialForm.materialName = item.materialName
  materialForm.materialType = item.materialType === 'finished' ? 'self_made' : item.materialType
  materialForm.materialGrade = item.materialGrade ?? ''
  materialForm.specification = item.specification ?? ''
  materialForm.note = item.note ?? ''
  materialDialogVisible.value = true
}

async function submitMaterial() {
  if (!activeProduct.value) return
  try {
    if (editingMaterialId.value) {
      await updateV2Material(editingMaterialId.value, {
        materialCode: materialForm.materialCode,
        materialType: materialForm.materialType,
        materialName: materialForm.materialName,
        materialGrade: materialForm.materialGrade,
        specification: materialForm.specification,
        note: materialForm.note,
      })
    } else {
      await addV2Material(activeProduct.value.id, materialForm)
    }
    materialDialogVisible.value = false
    await loadProducts()
    syncActiveProduct()
    ElMessage.success('物料已添加')
  } catch {
    ElMessage.error('物料保存失败；已被业务引用的物料不能修改类型或编号')
  }
}

const activeCustomerCodes = computed(() => activeProduct.value?.customerCodes ?? [])
const activeMaterials = computed(() => activeProduct.value?.materials ?? [])

async function switchUser() {
  await authStore.logout()
  router.replace('/login')
}

onMounted(async () => {
  try {
    treatments.value = await queryV2SurfaceTreatments()
  } catch {
    ElMessage.error('客户表面处理资料加载失败')
  }
  await loadProducts()
})
</script>

<template>
  <main class="page-shell">
    <header class="page-header">
      <div>
        <span>工程部</span>
        <h1>产品资料</h1>
      </div>
      <div class="header-actions">
        <ElButton @click="router.push('/dashboard')">产品总览</ElButton>
        <ElButton @click="router.push('/dashboard/master-data')">基础资料</ElButton>
        <ElInput
          v-model="keyword"
          clearable
          placeholder="搜索厂编或产品名称"
          @keyup.enter="loadProducts"
        />
        <ElButton @click="loadProducts">查询</ElButton>
        <ElButton type="primary" @click="openProductDialog">新增产品</ElButton>
        <ElButton @click="switchUser">切换用户</ElButton>
      </div>
    </header>

    <section v-loading="loading" class="content-card">
      <ElTable :data="products" stripe>
        <ElTableColumn prop="factoryCode" label="厂编" min-width="120" />
        <ElTableColumn prop="productName" label="产品名称" min-width="230" />
        <ElTableColumn label="客户/客编" min-width="260">
          <template #default="{ row }">
            <div v-for="item in row.customerCodes" :key="item.id">
              {{ item.customerName }} / {{ item.customerProductCode }}
            </div>
          </template>
        </ElTableColumn>
        <ElTableColumn label="物料" width="90">
          <template #default="{ row }">{{ row.materials.length }}</template>
        </ElTableColumn>
        <ElTableColumn label="状态" width="90">
          <template #default="{ row }">
            <ElTag :type="row.status === 'published' ? 'success' : 'info'">
              {{ productStatusLabels[row.status] }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <ElButton text @click="openDetail(row)">查看和编辑</ElButton>
            <ElButton
              text
              @click="router.push(`/dashboard/engineering/products/${row.id}/structure`)"
            >
              BOM/组成
            </ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty v-if="!loading && products.length === 0" description="暂无产品资料" />
    </section>

    <ElDialog v-model="productDialogVisible" title="新增产品" width="1000px">
      <ElForm label-position="top">
        <div class="two-columns">
          <ElFormItem label="厂编" required>
            <ElInput
              v-model="productForm.factoryCode"
              placeholder="例如 Z8412"
              @input="refreshProductMaterialCodes"
            />
          </ElFormItem>
          <ElFormItem label="产品名称" required>
            <ElInput v-model="productForm.productName" />
          </ElFormItem>
        </div>
        <ElDivider content-position="left">客户与客编</ElDivider>
        <div v-for="(item, index) in productForm.customerCodes" :key="index" class="form-row">
          <ElInput v-model="item.customerName" placeholder="客户名称" />
          <ElInput v-model="item.customerProductCode" placeholder="客编" />
          <ElSelect v-model="item.treatmentIds" multiple placeholder="允许的表面处理">
            <ElOption
              v-for="treatment in treatmentOptions(item.customerName)"
              :key="treatment.id"
              :label="treatment.treatmentName"
              :value="treatment.id"
            />
          </ElSelect>
          <ElButton type="danger" text @click="productForm.customerCodes.splice(index, 1)">
            删除
          </ElButton>
        </div>
        <ElButton @click="addCustomerRow">添加客户客编</ElButton>

        <ElDivider content-position="left">配件与半成品</ElDivider>
        <div v-for="(item, index) in productForm.materials" :key="index" class="material-row">
          <ElSelect v-model="item.materialType" @change="changeNewMaterialType">
            <ElOption label="自制配件" value="self_made" />
            <ElOption label="外购配件" value="purchased" />
            <ElOption label="半成品" value="semi_finished" />
          </ElSelect>
          <ElInput
            v-model="item.materialCode"
            :disabled="item.materialType === 'semi_finished'"
            placeholder="配件编号/半成品自动生成"
          />
          <ElInput v-model="item.materialName" placeholder="名称" />
          <ElInput v-model="item.materialGrade" placeholder="材质" />
          <ElInput v-model="item.specification" placeholder="规格" />
          <ElInput v-model="item.note" placeholder="备注" />
          <ElButton type="danger" text @click="removeNewMaterial(index)">
            删除
          </ElButton>
        </div>
        <ElButton @click="addMaterialRow">添加物料</ElButton>
      </ElForm>
      <template #footer>
        <ElButton @click="productDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitProduct">保存产品</ElButton>
      </template>
    </ElDialog>

    <ElDrawer v-model="detailDrawerVisible" title="查看和编辑产品" size="65%">
      <template v-if="activeProduct">
        <div class="detail-actions">
          <ElButton
            v-if="activeProduct.status === 'draft'"
            type="success"
            @click="publishProduct(activeProduct)"
          >
            发布产品
          </ElButton>
          <ElButton
            v-if="activeProduct.status === 'published'
              && authStore.hasPermission('product:manage')"
            type="danger"
            @click="deactivateProduct(activeProduct)"
          >
            停用产品
          </ElButton>
          <ElButton
            v-if="activeProduct.status === 'draft'"
            @click="editProductName(activeProduct)"
          >
            编辑产品名称
          </ElButton>
          <ElButton @click="openCustomerDialog(activeProduct)">添加客编</ElButton>
          <ElButton
            v-if="activeProduct.status === 'draft'"
            type="primary"
            @click="openMaterialDialog(activeProduct)"
          >
            添加物料
          </ElButton>
        </div>
        <ElDescriptions :column="2" border>
          <ElDescriptionsItem label="厂编">{{ activeProduct.factoryCode }}</ElDescriptionsItem>
          <ElDescriptionsItem label="产品名称">
            {{ activeProduct.productName }}
          </ElDescriptionsItem>
        </ElDescriptions>
        <h3>客户与客编</h3>
        <ElTable :data="activeCustomerCodes" size="small">
          <ElTableColumn prop="customerName" label="客户" />
          <ElTableColumn prop="customerProductCode" label="客编" />
          <ElTableColumn label="操作" width="90">
            <template #default="{ row }">
              <ElButton text @click="editCustomerCode(activeProduct, row)">编辑</ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
        <h3>物料</h3>
        <ElTable :data="activeMaterials" size="small">
          <ElTableColumn prop="materialCode" label="编号" />
          <ElTableColumn prop="materialName" label="名称" />
          <ElTableColumn label="类型">
            <template #default="{ row }">{{ materialTypeLabels[row.materialType] }}</template>
          </ElTableColumn>
          <ElTableColumn prop="materialGrade" label="材质" />
          <ElTableColumn prop="specification" label="规格" />
          <ElTableColumn prop="note" label="备注" />
          <ElTableColumn label="操作" width="90">
            <template #default="{ row }">
              <ElButton
                v-if="activeProduct.status === 'draft' && row.materialType !== 'finished'"
                text
                @click="editMaterial(activeProduct, row)"
              >
                编辑
              </ElButton>
            </template>
          </ElTableColumn>
        </ElTable>
      </template>
    </ElDrawer>

    <ElDialog
      v-model="customerDialogVisible"
      :title="editingCustomerCodeId ? '编辑客户客编' : '添加客户客编'"
      width="520px"
    >
      <ElForm label-position="top">
        <ElFormItem label="客户名称">
          <ElInput v-model="customerForm.customerName" :disabled="Boolean(editingCustomerCodeId)" />
        </ElFormItem>
        <ElFormItem label="客编">
          <ElInput
            v-model="customerForm.customerProductCode"
            :disabled="Boolean(editingCustomerCodeId)"
          />
        </ElFormItem>
        <ElFormItem label="允许的表面处理">
          <ElSelect v-model="customerForm.treatmentIds" multiple>
            <ElOption
              v-for="item in treatmentOptions(customerForm.customerName)"
              :key="item.id"
              :label="item.treatmentName"
              :value="item.id"
            />
          </ElSelect>
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="customerDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitCustomerCode">保存</ElButton>
      </template>
    </ElDialog>

    <ElDialog
      v-model="materialDialogVisible"
      :title="editingMaterialId ? '编辑物料' : '添加物料'"
      width="620px"
    >
      <ElForm label-position="top">
        <ElFormItem label="类型">
          <ElSelect v-model="materialForm.materialType" @change="changeMaterialDialogType">
            <ElOption label="自制配件" value="self_made" />
            <ElOption label="外购配件" value="purchased" />
            <ElOption label="半成品" value="semi_finished" />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="编号">
          <ElInput
            v-model="materialForm.materialCode"
            :disabled="!editingMaterialId && materialForm.materialType === 'semi_finished'"
            placeholder="半成品编号由系统生成"
          />
        </ElFormItem>
        <ElFormItem label="名称"><ElInput v-model="materialForm.materialName" /></ElFormItem>
        <ElFormItem label="材质"><ElInput v-model="materialForm.materialGrade" /></ElFormItem>
        <ElFormItem label="规格"><ElInput v-model="materialForm.specification" /></ElFormItem>
        <ElFormItem label="备注"><ElInput v-model="materialForm.note" /></ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="materialDialogVisible = false">取消</ElButton>
        <ElButton type="primary" @click="submitMaterial">保存</ElButton>
      </template>
    </ElDialog>
  </main>
</template>

<style scoped>
.page-shell { min-height: 100vh; padding: 22px; background: var(--erp-bg); }
.page-header,
.content-card {
  border: 1px solid var(--erp-border);
  border-radius: 8px;
  background: #fff;
  box-shadow: var(--erp-shadow-sm);
}
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 16px 20px;
}
.page-header span { color: var(--erp-primary); font-size: 12px; font-weight: 700; }
.page-header h1 { margin: 6px 0 0; }
.header-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
.header-actions :deep(.el-input) { width: 260px; }
.content-card { padding: 18px; }
.detail-actions { display: flex; justify-content: flex-end; gap: 8px; margin-bottom: 16px; }
.two-columns { display: grid; grid-template-columns: 1fr 2fr; gap: 14px; }
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.3fr auto;
  gap: 10px;
  margin-bottom: 10px;
}
.material-row {
  display: grid;
  grid-template-columns: 130px 1fr 1fr 100px 1fr 1fr auto;
  gap: 8px;
  margin-bottom: 10px;
}
h3 { margin-top: 24px; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .header-actions,
  .two-columns,
  .form-row,
  .material-row { display: grid; grid-template-columns: 1fr; width: 100%; }
  .header-actions :deep(.el-input) { width: 100%; }
}
</style>
