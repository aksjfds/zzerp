const colorVariables = {
  primary: '--erp-primary',
  primaryContainer: '--erp-primary-soft',
  success: '--erp-success',
  warning: '--erp-warning',
  outline: '--erp-text-muted',
  outlineVariant: '--erp-border-strong',
  surface: '--erp-surface',
  text: '--erp-text',
  flowProduction: '--flow-production',
  flowProductionContainer: '--flow-production-container',
  flowOutsource: '--flow-outsource',
  flowOutsourceContainer: '--flow-outsource-container',
  flowSupplierProcessing: '--flow-supplier-processing',
  flowSupplierProcessingContainer: '--flow-supplier-processing-container',
  flowAssembly: '--flow-assembly',
  flowAssemblyContainer: '--flow-assembly-container',
  flowFinished: '--flow-finished',
  flowFinishedContainer: '--flow-finished-container',
  flowQc: '--flow-qc',
  flowQcContainer: '--flow-qc-container',
} as const

export type FlowColors = Record<keyof typeof colorVariables, string>

/** Read after mounting a canvas so the global stylesheet is already applied. */
export function readFlowColors(): FlowColors {
  const styles = getComputedStyle(document.documentElement)
  return Object.fromEntries(Object.entries(colorVariables).map(([key, variable]) => {
    const value = styles.getPropertyValue(variable).trim()
    if (!value) throw new Error(`流程图主题缺少变量 ${variable}`)
    return [key, value]
  })) as FlowColors
}
