const businessDateTime = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

export function formatBusinessDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  // Already formatted business times have no offset and must not be reinterpreted.
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) return value
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const parts = Object.fromEntries(businessDateTime.formatToParts(date).map(part => [part.type, part.value]))
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}
