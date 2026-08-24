type PrintFrameOptions = {
  width: string
  height: string
  pageStyle: string
}

const activePrintFrames = new Set<HTMLIFrameElement>()

export function printElement(element: HTMLElement, options: PrintFrameOptions) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.position = 'fixed'
  frame.style.left = '-12000px'
  frame.style.top = '0'
  frame.style.width = options.width
  frame.style.height = options.height
  frame.style.border = '0'

  const styles = [...document.head.querySelectorAll('style, link[rel="stylesheet"]')]
    .map(node => node.outerHTML)
    .join('')

  function removeFrame() {
    activePrintFrames.delete(frame)
    frame.remove()
  }

  frame.addEventListener('load', () => {
    const printWindow = frame.contentWindow
    if (!printWindow) {
      removeFrame()
      return
    }
    printWindow.addEventListener('afterprint', removeFrame, { once: true })
    printWindow.focus()
    printWindow.print()
  }, { once: true })
  frame.addEventListener('error', removeFrame, { once: true })
  frame.srcdoc = `<!doctype html>
    <html>
      <head>
        <base href="${document.baseURI}">
        ${styles}
        <style>${options.pageStyle}</style>
      </head>
      <body>${element.outerHTML}</body>
    </html>`
  activePrintFrames.add(frame)
  document.body.appendChild(frame)
  window.setTimeout(removeFrame, 120_000)
}
