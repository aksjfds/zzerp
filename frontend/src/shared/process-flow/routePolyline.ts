type FlowPoint = { x: number; y: number }
type FlowObstacle = {
  left: number
  right: number
  top: number
  bottom: number
}

type RouteState = {
  point: FlowPoint
  direction: 'h' | 'v' | ''
  cost: number
  key: string
}

const EDGE_NODE_CLEARANCE = 20
const BEND_COST = 1_000_000_000

function horizontalAnchor(anchorId: string | undefined, point: FlowPoint, node: FlowPoint) {
  if (anchorId?.endsWith('_1') || anchorId?.endsWith('_3')) return true
  if (anchorId?.endsWith('_0') || anchorId?.endsWith('_2')) return false
  return Math.abs(point.x - node.x) >= Math.abs(point.y - node.y)
}

function minimalOrthogonalPoints(
  start: FlowPoint,
  end: FlowPoint,
  sourceHorizontal: boolean,
  targetHorizontal: boolean,
) {
  if (start.x === end.x || start.y === end.y) return [start, end]
  if (sourceHorizontal !== targetHorizontal) {
    return [
      start,
      sourceHorizontal
        ? { x: end.x, y: start.y }
        : { x: start.x, y: end.y },
      end,
    ]
  }
  if (sourceHorizontal) {
    const middleX = (start.x + end.x) / 2
    return [start, { x: middleX, y: start.y }, { x: middleX, y: end.y }, end]
  }
  const middleY = (start.y + end.y) / 2
  return [start, { x: start.x, y: middleY }, { x: end.x, y: middleY }, end]
}

export function obstacleAwarePoints(
  start: FlowPoint,
  end: FlowPoint,
  sourceAnchorId: string | undefined,
  targetAnchorId: string | undefined,
  sourceNodeId: string,
  targetNodeId: string,
  nodes: Array<{ id: string; x: number; y: number; width: number; height: number }>,
) {
  const obstacles = nodes.map(node => ({
    left: node.x - node.width / 2 - (node.id === sourceNodeId || node.id === targetNodeId ? 0 : EDGE_NODE_CLEARANCE),
    right: node.x + node.width / 2 + (node.id === sourceNodeId || node.id === targetNodeId ? 0 : EDGE_NODE_CLEARANCE),
    top: node.y - node.height / 2 - (node.id === sourceNodeId || node.id === targetNodeId ? 0 : EDGE_NODE_CLEARANCE),
    bottom: node.y + node.height / 2 + (node.id === sourceNodeId || node.id === targetNodeId ? 0 : EDGE_NODE_CLEARANCE),
  }))
  const sourceNode = nodes.find(node => node.id === sourceNodeId)
  const targetNode = nodes.find(node => node.id === targetNodeId)
  const preferred = preferredOrthogonalPoints(
    start,
    end,
    sourceAnchorId,
    targetAnchorId,
    sourceNode ?? start,
    targetNode ?? end,
  )
  if (routeAvoidsNodes(preferred, obstacles)
    && validSourceStep(preferred[0]!, preferred[1]!, sourceAnchorId)
    && validTargetStep(
      preferred[preferred.length - 2]!,
      preferred[preferred.length - 1]!,
      targetAnchorId,
    )) {
    return preferred
  }
  const obstacleX = obstacles.flatMap(item => [item.left, item.right])
  const obstacleY = obstacles.flatMap(item => [item.top, item.bottom])
  const xValues = sortedUnique([
    start.x,
    end.x,
    ...obstacleX,
    Math.min(...obstacleX) - EDGE_NODE_CLEARANCE,
    Math.max(...obstacleX) + EDGE_NODE_CLEARANCE,
  ])
  const yValues = sortedUnique([
    start.y,
    end.y,
    ...obstacleY,
    Math.min(...obstacleY) - EDGE_NODE_CLEARANCE,
    Math.max(...obstacleY) + EDGE_NODE_CLEARANCE,
  ])
  const startKey = pointKey(start)
  const endKey = pointKey(end)
  const queue: RouteState[] = [{ point: start, direction: '', cost: 0, key: `${startKey}:` }]
  const costs = new Map([[`${startKey}:`, 0]])
  const previous = new Map<string, string>()
  const points = new Map<string, FlowPoint>([[`${startKey}:`, start]])
  let finalKey: string | undefined

  while (queue.length) {
    const current = popRouteState(queue)!
    if (current.cost !== costs.get(current.key)) continue
    if (pointKey(current.point) === endKey) {
      finalKey = current.key
      break
    }
    for (const next of adjacentPoints(current.point, xValues, yValues)) {
      const direction = current.point.y === next.y ? 'h' : 'v'
      if (!current.direction && !validSourceStep(current.point, next, sourceAnchorId)) continue
      if (pointKey(next) === endKey && !validTargetStep(current.point, next, targetAnchorId)) continue
      if (pointInsideObstacle(next, obstacles, start, end)) continue
      if (obstacles.some(item => segmentCrossesObstacle(current.point, next, item))) continue
      const bend = current.direction && current.direction !== direction ? 1 : 0
      const length = Math.abs(next.x - current.point.x) + Math.abs(next.y - current.point.y)
      const cost = current.cost + bend * BEND_COST + length
      const key = `${pointKey(next)}:${direction}`
      if (cost >= (costs.get(key) ?? Number.POSITIVE_INFINITY)) continue
      costs.set(key, cost)
      previous.set(key, current.key)
      points.set(key, next)
      pushRouteState(queue, { point: next, direction, cost, key })
    }
  }

  if (!finalKey) {
    return minimalOrthogonalPoints(
      start,
      end,
      horizontalAnchor(sourceAnchorId, start, nodes.find(node => node.id === sourceNodeId) ?? start),
      horizontalAnchor(targetAnchorId, end, nodes.find(node => node.id === targetNodeId) ?? end),
    )
  }
  const route: FlowPoint[] = []
  for (let key: string | undefined = finalKey; key; key = previous.get(key)) {
    route.push(points.get(key)!)
  }
  return simplifyPoints(route.reverse())
}

function sortedUnique(values: number[]) {
  return [...new Set(values)].sort((left, right) => left - right)
}

function pointKey(point: FlowPoint) {
  return `${point.x},${point.y}`
}

function preferredOrthogonalPoints(
  start: FlowPoint,
  end: FlowPoint,
  sourceAnchorId: string | undefined,
  targetAnchorId: string | undefined,
  sourceNode: FlowPoint,
  targetNode: FlowPoint,
) {
  if (start.x === end.x || start.y === end.y) return [start, end]
  const sourceHorizontal = horizontalAnchor(sourceAnchorId, start, sourceNode)
  const targetHorizontal = horizontalAnchor(targetAnchorId, end, targetNode)
  if (sourceHorizontal !== targetHorizontal) {
    return [
      start,
      sourceHorizontal
        ? { x: end.x, y: start.y }
        : { x: start.x, y: end.y },
      end,
    ]
  }
  if (Math.abs(targetNode.x - sourceNode.x) >= Math.abs(targetNode.y - sourceNode.y)) {
    const middleX = (sourceNode.x + targetNode.x) / 2
    return simplifyPoints([
      start,
      { x: middleX, y: start.y },
      { x: middleX, y: end.y },
      end,
    ])
  }
  const middleY = (sourceNode.y + targetNode.y) / 2
  return simplifyPoints([
    start,
    { x: start.x, y: middleY },
    { x: end.x, y: middleY },
    end,
  ])
}

function routeAvoidsNodes(points: FlowPoint[], obstacles: FlowObstacle[]) {
  return points.slice(0, -1).every((point, index) => (
    !obstacles.some(item => segmentCrossesObstacle(point, points[index + 1]!, item))
  ))
}

function routeStateBefore(left: RouteState, right: RouteState) {
  return left.cost < right.cost || (left.cost === right.cost && left.key < right.key)
}

function pushRouteState(queue: RouteState[], state: RouteState) {
  queue.push(state)
  let index = queue.length - 1
  while (index > 0) {
    const parent = Math.floor((index - 1) / 2)
    if (routeStateBefore(queue[parent]!, queue[index]!)) break
    const parentState = queue[parent]!
    queue[parent] = queue[index]!
    queue[index] = parentState
    index = parent
  }
}

function popRouteState(queue: RouteState[]) {
  const first = queue[0]
  const last = queue.pop()
  if (!queue.length || !last) return first
  queue[0] = last
  let index = 0
  while (true) {
    const left = index * 2 + 1
    const right = left + 1
    let best = index
    if (left < queue.length && routeStateBefore(queue[left]!, queue[best]!)) best = left
    if (right < queue.length && routeStateBefore(queue[right]!, queue[best]!)) best = right
    if (best === index) break
    const currentState = queue[index]!
    queue[index] = queue[best]!
    queue[best] = currentState
    index = best
  }
  return first
}

function adjacentPoints(point: FlowPoint, xValues: number[], yValues: number[]) {
  const xIndex = xValues.indexOf(point.x)
  const yIndex = yValues.indexOf(point.y)
  return [
    xValues[xIndex - 1] === undefined ? null : { x: xValues[xIndex - 1]!, y: point.y },
    xValues[xIndex + 1] === undefined ? null : { x: xValues[xIndex + 1]!, y: point.y },
    yValues[yIndex - 1] === undefined ? null : { x: point.x, y: yValues[yIndex - 1]! },
    yValues[yIndex + 1] === undefined ? null : { x: point.x, y: yValues[yIndex + 1]! },
  ].filter((item): item is FlowPoint => item !== null)
}

function pointInsideObstacle(
  point: FlowPoint,
  obstacles: FlowObstacle[],
  start: FlowPoint,
  end: FlowPoint,
) {
  if (pointKey(point) === pointKey(start) || pointKey(point) === pointKey(end)) return false
  return obstacles.some(item => (
    point.x > item.left && point.x < item.right && point.y > item.top && point.y < item.bottom
  ))
}

function segmentCrossesObstacle(start: FlowPoint, end: FlowPoint, obstacle: FlowObstacle) {
  if (start.y === end.y) {
    return start.y > obstacle.top
      && start.y < obstacle.bottom
      && Math.max(start.x, end.x) > obstacle.left
      && Math.min(start.x, end.x) < obstacle.right
  }
  return start.x > obstacle.left
    && start.x < obstacle.right
    && Math.max(start.y, end.y) > obstacle.top
    && Math.min(start.y, end.y) < obstacle.bottom
}

function validSourceStep(start: FlowPoint, next: FlowPoint, anchorId: string | undefined) {
  if (anchorId?.endsWith('_0')) return next.y < start.y
  if (anchorId?.endsWith('_1')) return next.x > start.x
  if (anchorId?.endsWith('_2')) return next.y > start.y
  if (anchorId?.endsWith('_3')) return next.x < start.x
  return true
}

function validTargetStep(previous: FlowPoint, end: FlowPoint, anchorId: string | undefined) {
  if (anchorId?.endsWith('_0')) return previous.y < end.y
  if (anchorId?.endsWith('_1')) return previous.x > end.x
  if (anchorId?.endsWith('_2')) return previous.y > end.y
  if (anchorId?.endsWith('_3')) return previous.x < end.x
  return true
}

function simplifyPoints(points: FlowPoint[]) {
  return points.filter((point, index) => {
    if (index === 0 || index === points.length - 1) return true
    const previous = points[index - 1]!
    const next = points[index + 1]!
    return !(
      (previous.x === point.x && point.x === next.x)
      || (previous.y === point.y && point.y === next.y)
    )
  })
}
