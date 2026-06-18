import type {
    CreateWorkOrderPayload,
    MoveRepositoryQuantityPayload,
    OperationRecord,
    Procedure,
    WorkOrderItem,
    WorkOrderQuery,
    WorkOrderStatus,
} from '@/types/workorder'
import { service } from './request'

type ApiWorkOrder = {
    id: number | string
    item: string
    quantity: number
    createdAt?: string
    steps: Array<{
        name: Procedure
        quantity: number
    }>
}

function getWorkOrderStatus(order: Pick<WorkOrderItem, 'quantity' | 'steps'>): WorkOrderStatus {
    if (order.quantity > 0 && order.steps.every((step) => step.quantity === 0)) {
        return '已完成'
    }

    if (order.steps.some((step, index) => index > 0 && step.quantity > 0)) {
        return '加工中'
    }

    return '待开工'
}

function normalizeWorkOrder(order: ApiWorkOrder): WorkOrderItem {
    const workOrder = {
        id: `MO-${order.id}`,
        item: order.item,
        quantity: order.quantity,
        createdAt: order.createdAt,
        steps: order.steps,
    }

    return {
        ...workOrder,
        status: getWorkOrderStatus(workOrder),
    }
}

function parseWorkOrderId(orderId: string) {
    const value = orderId.replace(/^MO-/, '')
    const parsed = Number(value)

    if (!Number.isInteger(parsed) || parsed <= 0) {
        throw new Error('工单编号无效')
    }

    return parsed
}

export async function queryWorkOrders(query: WorkOrderQuery = {}) {
    const res = await service.get<{ data: ApiWorkOrder[] }>("/query_workorders")
    const workOrders = res.data.data.map(normalizeWorkOrder)

    const orderId = query.orderId?.trim().toLowerCase()
    const item = query.item?.trim().toLowerCase()

    const filtered = workOrders.filter((order) => {
        const matchOrderId = !orderId || order.id.toLowerCase().includes(orderId)
        const matchitem = !item || order.item.toLowerCase().includes(item)
        const matchStatus = !query.status || order.status === query.status
        const matchProcedure =
            !query.procedure || order.steps.some((step) => step.name === query.procedure)

        return matchOrderId && matchitem && matchStatus && matchProcedure
    })

    return filtered
}

export async function createWorkOrder(payload: CreateWorkOrderPayload) {
    const item = payload.item.trim()

    if (!item) {
        throw new Error('部件不能为空')
    }

    if (payload.quantity <= 0) {
        throw new Error('数量必须大于 0')
    }

    if (payload.procedures.length === 0) {
        throw new Error('至少需要配置一道工序')
    }

    const res = await service.post<{ data: ApiWorkOrder }>("/create_workorder", {
        item,
        quantity: payload.quantity,
        procedures: payload.procedures,
    })

    return normalizeWorkOrder(res.data.data)
}

export async function queryOperationRecords(orderId: string, item: string, repository: Procedure) {
    const res = await service.get<{ data: OperationRecord[] }>("/query_record_logs", {
        params: {
            order_id: parseWorkOrderId(orderId),
            item,
            repository,
        },
    })

    return res.data.data
}

function buildMovePayload(payload: MoveRepositoryQuantityPayload) {
    return {
        order_id: parseWorkOrderId(payload.orderId),
        item: payload.item,
        repository: payload.repository,
        quantity: payload.quantity,
        operator: payload.operator,
        worker: payload.worker,
        note: payload.note,
    }
}

export async function recordOutbound(payload: MoveRepositoryQuantityPayload) {
    await service.post("/record_outbound", {
        ...buildMovePayload(payload),
    })
}

export async function recordRework(payload: MoveRepositoryQuantityPayload) {
    await service.post("/record_rework", {
        ...buildMovePayload(payload),
    })
}
