import type { CreateWorkOrderPayload, WorkOrderItem, WorkOrderQuery } from '@/types/workorder'
import { service } from './request'

const mockWorkOrders: WorkOrderItem[] = [
    {
        id: 'MO-20260616-001',
        part: 'MOG3V45-过桥',
        quantity: 120,
        status: '加工中',
        createdAt: '2026-06-16',
        steps: [
            {
                name: '激光',
                inbound: 120,
                outbound: 120,
                outboundRecords: [
                    { id: 'R-001-1', quantity: 70, createdAt: '2026-06-16 09:12', operator: '张工' },
                    { id: 'R-001-2', quantity: 50, createdAt: '2026-06-16 10:24', operator: '张工' },
                ],
            },
            {
                name: 'CNC',
                inbound: 120,
                outbound: 86,
                outboundRecords: [
                    { id: 'R-001-3', quantity: 46, createdAt: '2026-06-16 13:18', operator: '李工' },
                    { id: 'R-001-4', quantity: 40, createdAt: '2026-06-16 15:06', operator: '李工' },
                ],
            },
            {
                name: '打磨',
                inbound: 86,
                outbound: 42,
                outboundRecords: [
                    { id: 'R-001-5', quantity: 42, createdAt: '2026-06-16 16:20', operator: '王工' },
                ],
            },
            {
                name: 'QC',
                inbound: 42,
                outbound: 18,
                outboundRecords: [
                    { id: 'R-001-6', quantity: 18, createdAt: '2026-06-16 17:05', operator: '赵工' },
                ],
            },
        ],
    },
    {
        id: 'MO-20260616-002',
        part: 'BRK8A12-固定座',
        quantity: 80,
        status: '待开工',
        createdAt: '2026-06-16',
        steps: [
            { name: '激光', inbound: 80, outbound: 0, outboundRecords: [] },
            { name: 'CNC', inbound: 0, outbound: 0, outboundRecords: [] },
            { name: 'QC', inbound: 0, outbound: 0, outboundRecords: [] },
        ],
    },
]

function cloneWorkOrders(workOrders: WorkOrderItem[]) {
    return structuredClone(workOrders)
}

function cloneWorkOrder(workOrder: WorkOrderItem) {
    return structuredClone(workOrder)
}

function getTodayText() {
    const date = new Date()
    const pad = (value: number) => String(value).padStart(2, '0')

    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export async function queryWorkOrders(query: WorkOrderQuery = {}) {

    // const res = await service.get("/query_workorders")
    const res = await service.get("")
    console.log(await res.data);
    

    const orderId = query.orderId?.trim().toLowerCase()
    const part = query.part?.trim().toLowerCase()

    const filtered = mockWorkOrders.filter((order) => {
        const matchOrderId = !orderId || order.id.toLowerCase().includes(orderId)
        const matchPart = !part || order.part.toLowerCase().includes(part)
        const matchStatus = !query.status || order.status === query.status
        const matchProcedure =
            !query.procedure || order.steps.some((step) => step.name === query.procedure)

        return matchOrderId && matchPart && matchStatus && matchProcedure
    })

    return cloneWorkOrders(filtered)
}

export async function createWorkOrder(payload: CreateWorkOrderPayload) {
    const part = payload.part.trim()

    if (!part) {
        throw new Error('部件不能为空')
    }

    if (payload.quantity <= 0) {
        throw new Error('数量必须大于 0')
    }

    if (payload.procedures.length === 0) {
        throw new Error('至少需要配置一道工序')
    }

    const workOrder: WorkOrderItem = {
        id: `MO-${Date.now()}`,
        part,
        quantity: payload.quantity,
        status: '待开工',
        createdAt: getTodayText(),
        steps: payload.procedures.map((name, index) => ({
            name,
            inbound: index === 0 ? payload.quantity : 0,
            outbound: 0,
            outboundRecords: [],
        })),
    }

    mockWorkOrders.unshift(workOrder)

    return cloneWorkOrder(workOrder)
}
