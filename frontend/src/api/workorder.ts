import type {
    CreateWorkOrderPayload,
    Procedure,
    WorkOrderItem,
    WorkOrderQuery,
    WorkOrderStatus,
} from '@/types/workorder'
import { service } from './request'

function cloneWorkOrders(workOrders: WorkOrderItem[]) {
    return structuredClone(workOrders)
}

function cloneWorkOrder(workOrder: WorkOrderItem) {
    return structuredClone(workOrder)
}

type ApiWorkOrder = {
    id: number | string
    item: string
    quantity: number
    createdAt?: string
    steps: Array<{
        name: Procedure
        inbound: number
        outbound: number
    }>
}

function getWorkOrderStatus(order: Pick<WorkOrderItem, 'quantity' | 'steps'>): WorkOrderStatus {
    const lastStep = order.steps[order.steps.length - 1]

    if (lastStep && lastStep.outbound >= order.quantity) {
        return '已完成'
    }

    if (order.steps.some((step) => step.outbound > 0)) {
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

    return cloneWorkOrders(filtered)
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

    return cloneWorkOrder(normalizeWorkOrder(res.data.data))
}
