import type { RepositoryItem } from './types'

type CardMode = 'production' | 'purchase' | 'assembly'

const statusLabels: Record<CardMode, Record<RepositoryItem['work_status'], string>> = {
  production: {
    unprocessed: '未开工',
    processing: '进行中',
    processing_completed: '进行中',
    qc: '进行中',
    rework: '进行中',
    completed: '已完成',
  },
  purchase: {
    unprocessed: '待采购',
    processing: '采购中',
    processing_completed: '到货完成',
    qc: '质检中',
    rework: '返工中',
    completed: '已入库',
  },
  assembly: {
    unprocessed: '未装配',
    processing: '装配中',
    processing_completed: '待处理',
    qc: '质检中',
    rework: '返工中',
    completed: '结单',
  },
}

export function repositoryStatusClass(status: RepositoryItem['work_status']) {
  return `repository-status--${status}`
}

export function repositoryStatusLabel(
  status: RepositoryItem['work_status'],
  mode: CardMode,
) {
  return statusLabels[mode][status]
}
