const STORAGE_PREFIX = 'zzerp.tableColumnWidths.'
const initializedTables = new WeakSet<HTMLElement>()
const pendingRestoreTables = new WeakSet<HTMLElement>()
const scheduledRestoreTables = new WeakSet<HTMLElement>()

type ResizeSession = {
  table: HTMLElement
  widths: number[]
}

let resizeSession: ResizeSession | null = null
let observer: MutationObserver | null = null

export function setupTableColumnWidthPersistence() {
  if (observer || typeof document === 'undefined') return
  observeTables(document.body)
  observer = new MutationObserver(mutations => mutations.forEach((mutation) => {
    mutation.addedNodes.forEach((node) => {
      if (node instanceof HTMLElement) observeTables(node)
    })
  }))
  observer.observe(document.body, { childList: true, subtree: true })
  document.addEventListener('mousedown', handleHeaderMouseDown, true)
  document.addEventListener('mouseup', handleHeaderMouseUp, true)
}

function observeTables(root: HTMLElement) {
  root.closest<HTMLElement>('.el-table') && initializeTable(root.closest<HTMLElement>('.el-table')!)
  if (root.matches('.el-table')) initializeTable(root)
  root.querySelectorAll<HTMLElement>('.el-table').forEach(initializeTable)
}

function initializeTable(table: HTMLElement) {
  if (initializedTables.has(table)) {
    scheduleRestore(table)
    return
  }
  if (pendingRestoreTables.has(table)) return
  pendingRestoreTables.add(table)
  restoreWhenReady(table, 0)
}

function scheduleRestore(table: HTMLElement) {
  if (scheduledRestoreTables.has(table)) return
  scheduledRestoreTables.add(table)
  requestAnimationFrame(() => {
    scheduledRestoreTables.delete(table)
    if (!table.isConnected) return
    const headers = leafHeaders(table)
    const widths = readStoredWidths(table, headers)
    if (widths) applyWidths(table, headers, widths)
  })
}

function restoreWhenReady(table: HTMLElement, attempt: number) {
  requestAnimationFrame(() => {
    if (!table.isConnected) {
      pendingRestoreTables.delete(table)
      return
    }
    const headers = leafHeaders(table)
    if (!headers.length) {
      if (attempt < 60) restoreWhenReady(table, attempt + 1)
      else pendingRestoreTables.delete(table)
      return
    }
    pendingRestoreTables.delete(table)
    initializedTables.add(table)
    const widths = readStoredWidths(table, headers)
    if (!widths) return
    applyWidths(table, headers, widths)
    requestAnimationFrame(() => applyWidths(table, leafHeaders(table), widths))
  })
}

function handleHeaderMouseDown(event: MouseEvent) {
  if (event.button !== 0) return
  const target = event.target
  if (!(target instanceof Element)) return
  const header = target.closest<HTMLElement>('.el-table__header-wrapper th')
  const table = header?.closest<HTMLElement>('.el-table')
  if (!header || !table) return
  const rect = header.getBoundingClientRect()
  if (Math.abs(event.clientX - rect.right) > 8) return
  const headers = leafHeaders(table)
  resizeSession = { table, widths: headers.map(item => item.getBoundingClientRect().width) }
}

function handleHeaderMouseUp() {
  const session = resizeSession
  resizeSession = null
  if (!session?.table.isConnected) return
  requestAnimationFrame(() => {
    const headers = leafHeaders(session.table)
    if (headers.length !== session.widths.length) return
    const widths = headers.map(item => Math.round(item.getBoundingClientRect().width))
    const changed = widths.some((width, index) => Math.abs(width - session.widths[index]!) >= 2)
    if (!changed) return
    localStorage.setItem(storageKey(session.table, headers), JSON.stringify(widths))
  })
}

function leafHeaders(table: HTMLElement) {
  const rows = table.querySelectorAll<HTMLTableRowElement>(
    ':scope > .el-table__inner-wrapper > .el-table__header-wrapper thead tr',
  )
  const row = rows[rows.length - 1]
  return row
    ? [...row.querySelectorAll<HTMLElement>(':scope > th')].filter(header => (
        !header.classList.contains('el-table__cell--selection')
        && !header.classList.contains('gutter')
      ))
    : []
}

function storageKey(table: HTMLElement, headers: HTMLElement[]) {
  const labels = headers.map(header => normalizedLabel(header.textContent)).join('|')
  const signature = `${labels}|${headers.length}`
  const matchingTables = [...document.querySelectorAll<HTMLElement>('.el-table')].filter((candidate) => {
    const candidateHeaders = leafHeaders(candidate)
    return `${candidateHeaders.map(header => normalizedLabel(header.textContent)).join('|')}|${candidateHeaders.length}` === signature
  })
  const occurrence = Math.max(matchingTables.indexOf(table), 0)
  return `${STORAGE_PREFIX}${location.pathname}.${hash(signature)}.${occurrence}`
}

function normalizedLabel(value: string | null) {
  return (value || '').replace(/\s+/g, ' ').trim()
}

function hash(value: string) {
  let result = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index)
    result = Math.imul(result, 16777619)
  }
  return (result >>> 0).toString(36)
}

function readStoredWidths(table: HTMLElement, headers: HTMLElement[]) {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey(table, headers)) || 'null')
    if (!Array.isArray(parsed) || parsed.length !== headers.length) return null
    const widths = parsed.map(Number)
    return widths.every(width => Number.isFinite(width) && width > 0) ? widths : null
  } catch {
    return null
  }
}

function applyWidths(table: HTMLElement, headers: HTMLElement[], widths: number[]) {
  if (headers.length !== widths.length) return
  headers.forEach((header, index) => {
    const columnName = [...header.classList].find(name => /_column_\d+$/.test(name))
    if (!columnName) return
    table.querySelectorAll<HTMLTableColElement>(`col[name="${columnName}"]`).forEach((column) => {
      column.width = String(widths[index])
      column.style.width = `${widths[index]}px`
    })
  })
}
