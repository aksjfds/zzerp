import type LogicFlow from '@logicflow/core'
import type { Ref } from 'vue'

export function installProductionFlowPan(
  container: Ref<HTMLDivElement | undefined>,
  getInstance: () => LogicFlow | null,
  closePopover: () => void,
) {
  let panPoint: { x: number; y: number } | null = null

  function onPointerDown(event: PointerEvent) {
    const instance = getInstance()
    if (event.button !== 0 || !instance) return
    const target = event.target
    if (!(target instanceof Element)
      || !target.closest('.lf-canvas-overlay')
      || target.closest('.lf-node, .lf-edge, .lf-control')) return
    closePopover()
    event.preventDefault()
    event.stopPropagation()
    panPoint = { x: event.clientX, y: event.clientY }
    container.value?.classList.add('is-canvas-panning')
  }

  function onPointerMove(event: PointerEvent) {
    const instance = getInstance()
    if (!panPoint || !instance) return
    event.preventDefault()
    instance.translate(event.clientX - panPoint.x, event.clientY - panPoint.y)
    panPoint = { x: event.clientX, y: event.clientY }
  }

  function onPointerUp() {
    if (!panPoint) return
    panPoint = null
    container.value?.classList.remove('is-canvas-panning')
  }

  container.value?.addEventListener('pointerdown', onPointerDown, true)
  document.addEventListener('pointermove', onPointerMove)
  document.addEventListener('pointerup', onPointerUp)

  return () => {
    container.value?.removeEventListener('pointerdown', onPointerDown, true)
    document.removeEventListener('pointermove', onPointerMove)
    document.removeEventListener('pointerup', onPointerUp)
  }
}
