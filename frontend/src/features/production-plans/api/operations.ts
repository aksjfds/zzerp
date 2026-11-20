import { service } from '@/api/request'

export type OperationKind = 'movement' | 'inspection' | 'rework' | 'warehouse' | 'outsource' | 'outsource_return' | 'purchase' | 'purchase_receipt'
export type Operation = {
  kind: OperationKind; id: number; label: string; order_no: string; product: string; material: string
  quantity: string; actor_username: string; created_at: string; note: string
  revoked_at: string | null; revoked_by: string | null; revoke_reason: string | null
}
export async function revokeOperation(row: Operation, reason: string) {
  await service.post(`/production-plans/operations/${row.kind}/${row.id}/revoke`, { reason })
}
