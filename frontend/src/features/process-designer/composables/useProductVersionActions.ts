import type { ComputedRef } from 'vue'
import type { Router } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getApiErrorDetail } from '@/api/request'
import type { useEngineeringProductsStore } from '../stores/engineeringProducts'
import type { ProductForm } from '../domain/types'

type Options = {
  form: ProductForm
  productId: ComputedRef<number | null>
  selectedVersion: ComputedRef<number | undefined>
  versionDirty: ComputedRef<boolean>
  router: Router
  store: ReturnType<typeof useEngineeringProductsStore>
  loadProductVersion: (version?: number) => Promise<void>
  reloadVersions: () => Promise<void>
}

export function useProductVersionActions(options: Options) {
  const {
    form,
    loadProductVersion,
    productId,
    reloadVersions,
    router,
    selectedVersion,
    store,
    versionDirty,
  } = options

  function replaceMode(mode: 'view' | 'edit') {
    return router.replace({
      query: { mode, ...(form.version ? { version: String(form.version) } : {}) },
    })
  }

  async function enterEditMode() {
    await replaceMode('edit')
  }

  async function returnViewMode() {
    if (versionDirty.value) {
      try {
        await ElMessageBox.confirm(
          '当前产品基础信息、BOM 或流程有未保存内容，返回查看会丢失修改，是否继续？',
          '未保存修改',
          {
            type: 'warning',
            confirmButtonText: '返回查看',
            cancelButtonText: '继续编辑',
          },
        )
      } catch {
        return
      }
      if (form.version) await loadProductVersion(form.version)
    }
    await replaceMode('view')
  }

  async function createVersion() {
    if (!productId.value || form.revision === null || !selectedVersion.value) return
    if (versionDirty.value) {
      ElMessage.warning('当前产品资料有未保存内容，请先保存后再创建新版本')
      return
    }
    try {
      const product = await store.createVersion(
        productId.value,
        form.revision,
        selectedVersion.value,
      )
      await reloadVersions()
      await loadProductVersion(product.version)
      ElMessage.success(`已创建 V${product.version}`)
    } catch (error) {
      ElMessage.error(getApiErrorDetail(error)?.message || '创建新版本失败')
    }
  }

  return { createVersion, enterEditMode, returnViewMode }
}
