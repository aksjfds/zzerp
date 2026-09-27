export const erpMotion = {
  duration: {
    control: 130,
    content: 180,
    reveal: 360,
    enter: 260,
    exit: 200,
    dialogEnter: 200,
    dialogExit: 160,
  },
  easing: {
    enter: 'cubic-bezier(0.22, 1, 0.36, 1)',
    exit: 'cubic-bezier(0.4, 0, 1, 1)',
  },
  stagger: 28,
  maxStagger: 140,
} as const

export const erpMotionStyles = {
  '--erp-motion-control': `${erpMotion.duration.control}ms`,
  '--erp-motion-content': `${erpMotion.duration.content}ms`,
  '--erp-motion-reveal': `${erpMotion.duration.reveal}ms`,
  '--erp-motion-enter': `${erpMotion.duration.enter}ms`,
  '--erp-motion-exit': `${erpMotion.duration.exit}ms`,
  '--erp-motion-dialog-enter': `${erpMotion.duration.dialogEnter}ms`,
  '--erp-motion-dialog-exit': `${erpMotion.duration.dialogExit}ms`,
  '--erp-motion-ease-enter': erpMotion.easing.enter,
  '--erp-motion-ease-exit': erpMotion.easing.exit,
  '--el-transition-duration': 'var(--erp-motion-content)',
  '--el-transition-duration-fast': 'var(--erp-motion-control)',
  '--el-transition-duration-slow': 'var(--erp-motion-enter)',
}
