import type { App, DirectiveBinding } from 'vue'
import { useAuthStore } from '@/stores/auth'

function updatePermission(el: HTMLElement, binding: DirectiveBinding<string | string[]>) {
  const authStore = useAuthStore()

  if (!authStore.hasPermission(binding.value)) {
    el.style.display = 'none'
    return
  }

  el.style.removeProperty('display')
}

export function setupPermission(app: App) {
  app.directive('permission', {
    mounted: updatePermission,
    updated: updatePermission,
  })
}
