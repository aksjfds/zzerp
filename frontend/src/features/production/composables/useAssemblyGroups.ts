import { computed, ref, type Ref } from 'vue'
import type { RepositoryItem } from '../domain/types'

export type AssemblyGroup = {
  key: string
  items: RepositoryItem[]
  capacity: number
  complete: boolean
  productName: string
  name: string
  orderNo: string
  status: RepositoryItem['work_status']
  arrivedAt: string | null
  sources: Array<{ name: string; available: number; required: number }>
  kind: 'current' | 'processing' | 'history'
}

function groupKind(item: RepositoryItem) {
  if (!item.card_key.startsWith('history:')) return 'current' as const
  return item.work_status === 'processing' ? 'processing' as const : 'history' as const
}

export function assemblyGroupKey(item: RepositoryItem) {
  return `${groupKind(item)}:${item.customer_order_item_id}:${item.flow_node_id}`
}

export function useAssemblyGroups(items: Ref<RepositoryItem[]>) {
  const selections = ref(new Map<number, RepositoryItem>())
  const selectedIds = computed(() => [...selections.value.keys()])
  const groups = computed<AssemblyGroup[]>(() => {
    const grouped = new Map<string, RepositoryItem[]>()
    items.value.forEach((item) => {
      const key = assemblyGroupKey(item)
      grouped.set(key, [...(grouped.get(key) || []), item])
    })
    return [...grouped.entries()].map(([key, groupItems]) => {
      const firstItem = groupItems[0]!
      const kind = groupKind(firstItem)
      const complete = groupItems.every(item => item.assembly_group_complete)
      const sources = new Map<string, RepositoryItem[]>()
      groupItems.forEach(item => sources.set(
        item.source_flow_node_id,
        [...(sources.get(item.source_flow_node_id) || []), item],
      ))
      return {
        key,
        items: groupItems,
        capacity: complete
          ? Math.min(...[...sources.values()].map(sourceItems => Math.floor(
            sourceItems.reduce((sum, item) => sum + item.available_quantity, 0)
              / sourceItems[0]!.assembly_unit_quantity,
          )))
          : 0,
        complete,
        productName: firstItem.product_name,
        name: complete
          ? firstItem.assembly_output_name
            || `${[...new Set(groupItems.map(item => item.part_name.replace(/装配体$/, '')))].join('-')}装配体`
          : `待装配物料：${[...new Set(groupItems.map(item => item.part_name))].join('、')}`,
        orderNo: firstItem.customer_order_no,
        status: groupItems.some(item => item.work_status === 'processing')
          ? 'processing'
          : groupItems.every(item => item.work_status === 'completed') ? 'completed' : 'unprocessed',
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
  function selectGroup(group: AssemblyGroup) {
    selections.value.clear()
    group.items.forEach((item) => {
      if (item.repository_id) selections.value.set(item.repository_id, item)
    })
  }
  return { clear: () => selections.value.clear(), groups, selectGroup, selectedIds }
}
