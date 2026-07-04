import { onBeforeUnmount, onMounted, type ComputedRef } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessageBox } from 'element-plus'

export function useUnsavedChangesGuard(isDirty: ComputedRef<boolean>) {
  function handleBeforeUnload(event: BeforeUnloadEvent) {
    if (!isDirty.value) return
    event.preventDefault()
    event.returnValue = ''
  }

  onBeforeRouteLeave(async () => {
    if (!isDirty.value) return true
    try {
      await ElMessageBox.confirm('当前页面有未保存的修改，确认离开？', '未保存修改', {
        type: 'warning',
        confirmButtonText: '离开',
        cancelButtonText: '继续编辑',
      })
      return true
    } catch {
      return false
    }
  })

  onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload))
  onBeforeUnmount(() => window.removeEventListener('beforeunload', handleBeforeUnload))
}
