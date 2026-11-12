import type { BomItem } from './types'

export function nextPartNumber(factoryCode: string, items: BomItem[]): string {
  const prefix = factoryCode.trim()
  if (!prefix) return ''
  const start = `${prefix}-`
  const numbers = items.flatMap(item => {
    const value = item.part_no.trim()
    if (!value.startsWith(start)) return []
    const suffix = value.slice(start.length)
    return /^\d+$/.test(suffix) ? [Number(suffix)] : []
  })
  return `${start}${String(Math.max(0, ...numbers) + 1).padStart(2, '0')}`
}
