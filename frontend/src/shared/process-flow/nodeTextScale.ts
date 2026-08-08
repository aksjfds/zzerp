const NODE_TEXT_SCALE_PROPERTY = '--process-node-text-scale'

export function updateProcessNodeTextScale(container: HTMLElement, canvasScale: number) {
  const textScale = canvasScale > 0 && canvasScale < 1 ? 1 / canvasScale : 1
  container.style.setProperty(NODE_TEXT_SCALE_PROPERTY, String(textScale))
}
