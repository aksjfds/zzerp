import type LogicFlow from '@logicflow/core'

type InteractionOptions = {
  container: () => HTMLDivElement | null
  logicFlow: () => LogicFlow | null
  fitCanvas: (logicFlow: LogicFlow) => void
}

export function createCanvasPointerInteractions(options: InteractionOptions) {
  let middlePanPoint: { x: number; y: number } | null = null
  let selectionStart: { clientX: number; clientY: number; x: number; y: number } | null = null
  let selectionBox: HTMLDivElement | null = null

  function middlePanStart(event: PointerEvent) {
    const element = options.container()
    if (event.button !== 1 || !options.logicFlow() || !element) return
    event.preventDefault()
    event.stopPropagation()
    middlePanPoint = { x: event.clientX, y: event.clientY }
    element.classList.add('is-middle-panning')
  }

  function middlePanMove(event: PointerEvent) {
    const logicFlow = options.logicFlow()
    if (!middlePanPoint || !logicFlow) return
    event.preventDefault()
    logicFlow.translate(event.clientX - middlePanPoint.x, event.clientY - middlePanPoint.y)
    middlePanPoint = { x: event.clientX, y: event.clientY }
  }

  function middlePanEnd(event: PointerEvent) {
    const element = options.container()
    if (event.button !== 1 || !middlePanPoint) return
    middlePanPoint = null
    element?.classList.remove('is-middle-panning')
  }

  function preventMiddleAuxClick(event: MouseEvent) {
    if (event.button === 1) event.preventDefault()
  }

  function overviewClick(event: MouseEvent) {
    const target = event.target
    const controlItem = target instanceof Element ? target.closest('.lf-control-item') : null
    if (!controlItem?.querySelector('.lf-control-fit')) return
    const logicFlow = options.logicFlow()
    if (!logicFlow) return
    event.preventDefault()
    event.stopPropagation()
    options.fitCanvas(logicFlow)
  }

  function selectionStartHandler(event: PointerEvent) {
    const logicFlow = options.logicFlow()
    const element = options.container()
    if (event.button !== 0 || !logicFlow || !element) return
    const target = event.target
    if (!(target instanceof Element)
      || !target.closest('.lf-canvas-overlay')
      || target.closest('.lf-node, .lf-edge, .lf-anchor, .lf-control, .lf-menu')) return
    event.preventDefault()
    event.stopPropagation()
    const rect = element.getBoundingClientRect()
    selectionStart = {
      clientX: event.clientX,
      clientY: event.clientY,
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    }
    logicFlow.clearSelectElements()
    selectionBox = document.createElement('div')
    selectionBox.className = 'process-selection-box'
    selectionBox.style.left = `${selectionStart.x}px`
    selectionBox.style.top = `${selectionStart.y}px`
    selectionBox.style.width = '0'
    selectionBox.style.height = '0'
    element.appendChild(selectionBox)
  }

  function selectionMove(event: PointerEvent) {
    const element = options.container()
    if (!selectionStart || !selectionBox || !element) return
    event.preventDefault()
    const rect = element.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    selectionBox.style.left = `${Math.min(selectionStart.x, x)}px`
    selectionBox.style.top = `${Math.min(selectionStart.y, y)}px`
    selectionBox.style.width = `${Math.abs(x - selectionStart.x)}px`
    selectionBox.style.height = `${Math.abs(y - selectionStart.y)}px`
  }

  function selectionEnd(event: PointerEvent) {
    const logicFlow = options.logicFlow()
    if (event.button !== 0 || !selectionStart || !logicFlow) return
    const start = selectionStart
    const width = Math.abs(event.clientX - start.clientX)
    const height = Math.abs(event.clientY - start.clientY)
    selectionStart = null
    selectionBox?.remove()
    selectionBox = null
    if (width < 6 || height < 6) return
    const startPoint = logicFlow.getPointByClient(start.clientX, start.clientY).domOverlayPosition
    const endPoint = logicFlow.getPointByClient(event.clientX, event.clientY).domOverlayPosition
    const leftTop: [number, number] = [
      Math.min(startPoint.x, endPoint.x), Math.min(startPoint.y, endPoint.y),
    ]
    const rightBottom: [number, number] = [
      Math.max(startPoint.x, endPoint.x), Math.max(startPoint.y, endPoint.y),
    ]
    logicFlow.graphModel
      .getAreaElement(leftTop, rightBottom, true, false, true)
      .filter(item => Boolean(logicFlow.getNodeModelById(item.id)))
      .forEach(node => logicFlow.selectElementById(node.id, true))
  }

  function bind(element: HTMLDivElement) {
    element.addEventListener('pointerdown', middlePanStart, true)
    element.addEventListener('pointerdown', selectionStartHandler, true)
    element.addEventListener('auxclick', preventMiddleAuxClick)
    element.addEventListener('click', overviewClick, true)
    document.addEventListener('pointermove', middlePanMove)
    document.addEventListener('pointermove', selectionMove)
    document.addEventListener('pointerup', middlePanEnd)
    document.addEventListener('pointerup', selectionEnd)
  }

  function dispose(element: HTMLDivElement | null) {
    element?.removeEventListener('pointerdown', middlePanStart, true)
    element?.removeEventListener('pointerdown', selectionStartHandler, true)
    element?.removeEventListener('auxclick', preventMiddleAuxClick)
    element?.removeEventListener('click', overviewClick, true)
    document.removeEventListener('pointermove', middlePanMove)
    document.removeEventListener('pointermove', selectionMove)
    document.removeEventListener('pointerup', middlePanEnd)
    document.removeEventListener('pointerup', selectionEnd)
    selectionBox?.remove()
    selectionBox = null
    selectionStart = null
    middlePanPoint = null
  }

  return { bind, dispose }
}
