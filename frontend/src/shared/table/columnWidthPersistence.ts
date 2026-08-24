import type { App, Directive, DirectiveBinding } from 'vue'

const STORAGE_PREFIX = 'zzerp.tableColumnWidths.'

type TableColumnWidths = Record<string, number>

type TableState = {
  key: string
  signature: string
  startWidths: number[] | null
  onMouseDown: (event: MouseEvent) => void
  onMouseUp: () => void
}

const tableStates = new WeakMap<HTMLElement, TableState>()

function tableElement(element: HTMLElement) {
  return element.matches('.el-table')
    ? element
    : element.querySelector<HTMLElement>('.el-table')
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

function normalizedLabel(value: string | null) {
  return (value || '').replace(/\s+/g, ' ').trim()
}

function columnKeys(headers: HTMLElement[]) {
  const occurrences = new Map<string, number>()
  return headers.map((header) => {
    const label = normalizedLabel(header.textContent) || '未命名列'
    const occurrence = occurrences.get(label) ?? 0
    occurrences.set(label, occurrence + 1)
    return occurrence ? `${label}#${occurrence + 1}` : label
  })
}

function columnSignature(headers: HTMLElement[]) {
  return columnKeys(headers).join('|')
}

function storageKey(key: string) {
  return `${STORAGE_PREFIX}${key}`
}

function readWidths(key: string): TableColumnWidths {
  try {
    const value = JSON.parse(localStorage.getItem(storageKey(key)) || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    return Object.fromEntries(
      Object.entries(value).filter((entry): entry is [string, number] => (
        typeof entry[1] === 'number'
        && Number.isFinite(entry[1])
        && entry[1] > 0
      )),
    )
  } catch {
    return {}
  }
}

function applyWidths(table: HTMLElement, headers: HTMLElement[], widths: TableColumnWidths) {
  columnKeys(headers).forEach((key, index) => {
    const width = widths[key]
    if (!width) return
    const columnName = [...headers[index]!.classList].find(name => /_column_\d+$/.test(name))
    if (!columnName) return
    table.querySelectorAll<HTMLTableColElement>(`col[name="${columnName}"]`).forEach((column) => {
      column.width = String(width)
      column.style.width = `${width}px`
    })
  })
}

function restoreWidths(table: HTMLElement, state: TableState) {
  requestAnimationFrame(() => {
    if (!table.isConnected) return
    const headers = leafHeaders(table)
    if (!headers.length) return
    state.signature = columnSignature(headers)
    applyWidths(table, headers, readWidths(state.key))
  })
}

function saveWidths(table: HTMLElement, state: TableState) {
  const headers = leafHeaders(table)
  if (!state.startWidths || headers.length !== state.startWidths.length) return
  const measured = headers.map(header => Math.round(header.getBoundingClientRect().width))
  if (!measured.some((width, index) => Math.abs(width - state.startWidths![index]!) >= 2)) {
    return
  }
  const stored = readWidths(state.key)
  columnKeys(headers).forEach((key, index) => {
    stored[key] = measured[index]!
  })
  localStorage.setItem(storageKey(state.key), JSON.stringify(stored))
}

function mountTable(element: HTMLElement, binding: DirectiveBinding<string>) {
  const table = tableElement(element)
  const key = binding.value?.trim()
  if (!table || !key) return
  const state: TableState = {
    key,
    signature: '',
    startWidths: null,
    onMouseDown: () => undefined,
    onMouseUp: () => undefined,
  }
  state.onMouseDown = (event) => {
    if (event.button !== 0) return
    const target = event.target
    if (!(target instanceof Element)) return
    const header = target.closest<HTMLElement>('.el-table__header-wrapper th')
    if (!header || header.closest('.el-table') !== table) return
    if (Math.abs(event.clientX - header.getBoundingClientRect().right) > 8) return
    state.startWidths = leafHeaders(table).map(item => item.getBoundingClientRect().width)
    document.addEventListener('mouseup', state.onMouseUp, { once: true })
  }
  state.onMouseUp = () => {
    requestAnimationFrame(() => saveWidths(table, state))
  }
  table.addEventListener('mousedown', state.onMouseDown, true)
  tableStates.set(table, state)
  restoreWidths(table, state)
}

function updateTable(element: HTMLElement, binding: DirectiveBinding<string>) {
  const table = tableElement(element)
  if (!table) return
  const state = tableStates.get(table)
  const key = binding.value?.trim()
  if (!state || !key) return
  if (state.key !== key) {
    state.key = key
    state.signature = ''
  }
  const signature = columnSignature(leafHeaders(table))
  if (signature && signature !== state.signature) restoreWidths(table, state)
}

function unmountTable(element: HTMLElement) {
  const table = tableElement(element)
  if (!table) return
  const state = tableStates.get(table)
  if (!state) return
  table.removeEventListener('mousedown', state.onMouseDown, true)
  document.removeEventListener('mouseup', state.onMouseUp)
  tableStates.delete(table)
}

const tableColumnWidths: Directive<HTMLElement, string> = {
  mounted: mountTable,
  updated: updateTable,
  beforeUnmount: unmountTable,
}

export function setupTableColumnWidthPersistence(app: App) {
  app.directive('table-column-widths', tableColumnWidths)
}
