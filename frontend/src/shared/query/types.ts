export type Page<T> = { data: T[]; total: number }
export type PageRequest = { page: number; pageSize: number; signal: AbortSignal }
