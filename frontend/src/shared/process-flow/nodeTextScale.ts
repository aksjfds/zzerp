const NODE_ANCHOR_SCALE_PROPERTY = '--process-node-anchor-scale'

export function updateProcessCanvasScale(
  container: HTMLElement,
  canvasScale: number,
) {
  const inverseScale = canvasScale > 0 && canvasScale < 1 ? 1 / canvasScale : 1
  container.style.setProperty(
    NODE_ANCHOR_SCALE_PROPERTY,
    String(Math.min(inverseScale, 2)),
  )
}
