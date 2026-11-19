export function printElement(element: HTMLElement, title: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const frame = document.createElement('iframe')
    frame.setAttribute('aria-hidden', 'true')
    Object.assign(frame.style, { position: 'fixed', left: '-12000px', top: '0', width: '800px', height: '1100px', border: '0' })
    let started = false
    const cleanup = () => { window.clearTimeout(timeout); frame.remove() }
    const fail = () => { cleanup(); reject(new Error('打印页面加载失败，请重试')) }
    const timeout = window.setTimeout(() => { if (started) cleanup(); else fail() }, 120_000)
    frame.addEventListener('error', fail, { once: true })
    frame.addEventListener('load', async () => {
      try {
        const target = frame.contentWindow
        if (!target) throw new Error('打印窗口不可用')
        target.document.title = title
        await target.document.fonts.ready
        if (!frame.isConnected) return
        target.addEventListener('afterprint', cleanup, { once: true })
        target.focus()
        started = true
        target.print()
        resolve()
      } catch { fail() }
    }, { once: true })
    const styles = [...document.head.querySelectorAll('style, link[rel="stylesheet"]')].map(node => node.outerHTML).join('')
    frame.srcdoc = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">${styles}
      <style>@page { size: A4 portrait; margin: 14mm; }
      html, body { margin: 0 !important; padding: 0 !important; height: auto !important; min-height: 0 !important; overflow: visible !important; background: white !important; }
      </style></head><body>${element.outerHTML}</body></html>`
    document.body.appendChild(frame)
  })
}
