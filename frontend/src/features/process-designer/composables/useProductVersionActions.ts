import { onScopeDispose, type ComputedRef } from 'vue'
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
  loadProductVersion: (version?: number) => Promise<boolean>
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

  let active = true
  onScopeDispose(() => { active = false })

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
      if (form.version && !await loadProductVersion(form.version)) return
    }
    await replaceMode('view')
  }

  async function createVersion() {
    if (!productId.value || form.revision === null || !selectedVersion.value) return
    if (versionDirty.value) {
      ElMessage.warning('当前产品资料有未保存内容，请先保存后再创建新外观版本')
      return
    }
    const id = productId.value
    const revision = form.revision
    const source = selectedVersion.value
    try {
      const { value } = await ElMessageBox.prompt('', '创建新外观版本', {
        inputPlaceholder: '例如：V2、金色、亮银',
        confirmButtonText: '创建',
        cancelButtonText: '取消',
        inputValidator: (value: string) => {
          const text = value.trim()
          return text.length >= 1 && text.length <= 100 || '外观版本须为1–100个字符'
        },
      })
      if (!active || productId.value !== id || form.revision !== revision || selectedVersion.value !== source) return
      const product = await store.createVersion(
        id,
        revision,
        value.trim(),
        source,
      )
      if (!active || productId.value !== id) return
      await reloadVersions()
      if (!await loadProductVersion(product.version)) return
      ElMessage.success(`已创建 ${product.version_value}`)
    } catch (error) {
      if (!active || error === 'cancel' || error === 'close') return
      ElMessage.error(getApiErrorDetail(error)?.message || '创建新外观版本失败')
    }
  }

  return { createVersion, enterEditMode, returnViewMode }
}
