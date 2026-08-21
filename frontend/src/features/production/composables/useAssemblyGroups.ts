import { computed, type Ref } from 'vue'
import type { RepositoryItem } from '../domain/types'

export type AssemblyGroup = {
  key: string
  items: RepositoryItem[]
  capacity: number
  complete: boolean
  productName: string
  workshopName: string
  name: string
  orderNo: string
  status: RepositoryItem['work_status']
  arrivedAt: string | null
  sources: Array<{ name: string; available: number; required: number }>
  kind: 'current' | 'processing' | 'history'
}

function groupKind(item: RepositoryItem) {
  if (!item.card_key.startsWith('history:')) return 'current' as const
  return item.work_status !== 'completed' ? 'processing' as const : 'history' as const
}

const statusPriority: Record<RepositoryItem['work_status'], number> = {
  completed: 0,
  unprocessed: 1,
  processing: 2,
  processing_completed: 3,
  qc: 4,
  rework: 5,
}

export function assemblyGroupKey(item: RepositoryItem) {
  return `${groupKind(item)}:${item.customer_order_item_id}:${item.flow_node_id}`
}

export function useAssemblyGroups(items: Ref<RepositoryItem[]>) {
  const groups = computed<AssemblyGroup[]>(() => {
    const grouped = new Map<string, RepositoryItem[]>()
    items.value.filter(item => item.node_type === 'assembly').forEach((item) => {
      const key = assemblyGroupKey(item)
      grouped.set(key, [...(grouped.get(key) || []), item])
    })
    return [...grouped.entries()].map(([key, groupItems]) => {
      const firstItem = groupItems[0]!
      const kind = groupKind(firstItem)
      const complete = kind !== 'current'
        || groupItems.every(item => item.assembly_group_complete)
      const sources = new Map<string, RepositoryItem[]>()
      groupItems.forEach(item => sources.set(
        item.assembly_material_key,
        [...(sources.get(item.assembly_material_key) || []), item],
      ))
      return {
        key,
        items: groupItems,
        capacity: kind === 'current' && complete
          ? Math.min(...[...sources.values()].map(sourceItems => Math.floor(
            sourceItems.reduce((sum, item) => sum + item.available_quantity, 0)
              / sourceItems[0]!.assembly_unit_quantity,
          )))
          : 0,
        complete,
        productName: firstItem.product_name,
        workshopName: firstItem.workshop_name || '多路车间',
        name: firstItem.assembly_output_name
          || `${[...new Set(groupItems.map(item => item.part_name.replace(/装配体$/, '')))].join('-')}装配体`,
        orderNo: firstItem.customer_order_no,
        status: groupItems.every(item => item.work_status === 'completed')
          ? 'completed'
          : groupItems
            .filter(item => item.work_status !== 'completed')
            .sort((a, b) => statusPriority[b.work_status] - statusPriority[a.work_status])[0]
            ?.work_status || 'unprocessed',
        arrivedAt: groupItems.map(item => item.arrived_at).filter(Boolean).sort().at(-1) || null,
        sources: [...sources.values()].map(sourceItems => ({
          name: sourceItems[0]!.part_name,
          available: sourceItems.reduce((sum, item) => sum + item.available_quantity, 0),
          required: sourceItems[0]!.assembly_unit_quantity,
        })),
        kind,
      }
    })
  })
  return { groups }
}
