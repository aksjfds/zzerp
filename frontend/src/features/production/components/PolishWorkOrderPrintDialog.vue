<script setup lang="ts">
import { computed } from 'vue'
import type { WorkOrder } from '../domain/types'

const props = defineProps<{
  modelValue: boolean
  item?: WorkOrder
}>()

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

type InspectionRow = {
  label: string
  ok: number | ''
  ng: number | ''
  qcWorker: string
  date: string
  defectReason: string
  returned: number | ''
}

const inspectionLabels = ['首批', '返修1', '返修2', '返修3', '返修4', '返修5', '返修6']
const inspectionRows = computed<InspectionRow[]>(() => inspectionLabels.map((label, index) => {
  const batch = props.item?.batches[index]
  if (!batch || batch.qualified_quantity === null) {
    return {
      label,
      ok: '',
      ng: '',
      qcWorker: '',
      date: '',
      defectReason: '',
      returned: '',
    }
  }
  return {
    label,
    ok: batch.qualified_quantity,
    ng: Math.max(batch.submitted_quantity - batch.qualified_quantity, 0),
    qcWorker: batch?.qc_worker_name || '',
    date: batch?.recorded_at?.slice(0, 10) || '',
    defectReason: batch?.defect_reason || '',
    returned: batch.rework_quantity ?? 0,
  }
}))

function inspectionRow(index: number): InspectionRow {
  return inspectionRows.value[index] ?? {
    label: '',
    ok: '',
    ng: '',
    qcWorker: '',
    date: '',
    defectReason: '',
    returned: '',
  }
}

function print() {
  const sheet = document.querySelector<HTMLElement>('.polish-print-sheet')
  if (!sheet) return

  document
    .querySelectorAll<HTMLIFrameElement>('iframe[data-polish-print-frame]')
    .forEach(frame => frame.remove())

  const frame = document.createElement('iframe')
  frame.dataset.polishPrintFrame = 'true'
  frame.setAttribute('aria-hidden', 'true')
  frame.style.position = 'fixed'
  frame.style.left = '-12000px'
  frame.style.top = '0'
  frame.style.width = '1120px'
  frame.style.height = '800px'
  frame.style.border = '0'

  const styles = [...document.head.querySelectorAll('style, link[rel="stylesheet"]')]
    .map(node => node.outerHTML)
    .join('')
  const printOverrides = `
    <style>
      @page { size: A4 landscape; margin: 12mm; }
      html, body {
        width: auto !important;
        height: auto !important;
        min-height: 0 !important;
        margin: 0 !important;
        overflow: visible !important;
        background: #fff !important;
      }
      body > .polish-print-sheet {
        display: block !important;
        position: static !important;
        width: 272mm !important;
        max-width: 272mm !important;
        height: auto !important;
        max-height: none !important;
        margin: 0 !important;
        overflow: visible !important;
      }
    </style>
  `

  frame.addEventListener('load', () => {
    const printWindow = frame.contentWindow
    if (!printWindow) {
      frame.remove()
      return
    }
    printWindow.addEventListener('afterprint', () => frame.remove(), { once: true })
    printWindow.focus()
    printWindow.print()
  }, { once: true })

  frame.srcdoc = `<!doctype html>
    <html>
      <head>
        <base href="${document.baseURI}">
        ${styles}
        ${printOverrides}
      </head>
      <body>${sheet.outerHTML}</body>
    </html>`
  document.body.appendChild(frame)
}
</script>

<template>
  <ElDialog
    :model-value="modelValue"
    
    width="min(1180px, 96vw)"
    append-to-body
    class="polish-print-dialog"
    :modal-class="modelValue
      ? 'polish-print-overlay polish-print-overlay--active'
      : 'polish-print-overlay'"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <article v-if="item" class="polish-print-sheet">
      <h1>磨房计件单</h1>

      <section class="document-info">
        <div><strong>产品型号：</strong><span>{{ item.factory_code }}</span></div>
        <div class="product-name"><strong>产品名称：</strong><span>{{ item.product_name }}</span></div>
        <div class="document-no"><strong>NO：</strong><span>{{ item.work_order_no }}</span></div>
        <div><strong>客户订单号：</strong><span>{{ item.customer_order_no }}</span></div>
        <div class="wide"><strong>加工项目：</strong><span>{{ item.procedure_name }}</span></div>
        <div><strong>生产单号：</strong><span /></div>
        <div class="wide"><strong>加工备注：</strong><span>{{ item.remark }}</span></div>
      </section>

      <table class="work-record">
        <colgroup>
          <col class="col-a">
          <col class="col-b">
          <col class="col-c">
          <col class="col-d">
          <col class="col-e">
          <col class="col-f">
          <col class="col-g">
          <col class="col-h">
          <col class="col-i">
          <col class="col-j">
          <col class="col-k">
          <col class="col-l">
          <col class="col-m">
        </colgroup>
        <tbody>
          <tr class="machine-row">
            <td colspan="3" class="left">加工机台：</td>
            <th colspan="7">Q检判定</th>
            <th colspan="3">检验结果/数量</th>
          </tr>
          <tr class="column-headings">
            <th>打磨数量</th>
            <th colspan="2">加工出</th>
            <th>次数</th>
            <th>OK</th>
            <th>NG</th>
            <th>QC签字</th>
            <th>日期</th>
            <th>不良原因</th>
            <th>实退</th>
            <th />
            <th>首检</th>
            <th />
          </tr>
          <tr>
            <td rowspan="2" class="quantity">{{ item.quantity }}</td>
            <th>日期</th>
            <th>时间</th>
            <td>{{ inspectionRow(0).label }}</td>
            <td>{{ inspectionRow(0).ok }}</td>
            <td>{{ inspectionRow(0).ng }}</td>
            <td>{{ inspectionRow(0).qcWorker }}</td>
            <td>{{ inspectionRow(0).date }}</td>
            <td>{{ inspectionRow(0).defectReason }}</td>
            <td>{{ inspectionRow(0).returned }}</td>
            <td rowspan="3" class="vertical-label">良品</td>
            <td>返修</td>
            <td />
          </tr>
          <tr>
            <td />
            <td />
            <td>{{ inspectionRow(1).label }}</td>
            <td>{{ inspectionRow(1).ok }}</td>
            <td>{{ inspectionRow(1).ng }}</td>
            <td>{{ inspectionRow(1).qcWorker }}</td>
            <td>{{ inspectionRow(1).date }}</td>
            <td>{{ inspectionRow(1).defectReason }}</td>
            <td>{{ inspectionRow(1).returned }}</td>
            <td>遗失</td>
            <td />
          </tr>
          <tr>
            <th rowspan="2">清洗确认</th>
            <th>出清洗数</th>
            <th>签收人：</th>
            <td>{{ inspectionRow(2).label }}</td>
            <td>{{ inspectionRow(2).ok }}</td>
            <td>{{ inspectionRow(2).ng }}</td>
            <td>{{ inspectionRow(2).qcWorker }}</td>
            <td>{{ inspectionRow(2).date }}</td>
            <td>{{ inspectionRow(2).defectReason }}</td>
            <td>{{ inspectionRow(2).returned }}</td>
            <td>取样</td>
            <td />
          </tr>
          <tr>
            <td />
            <td />
            <td>{{ inspectionRow(3).label }}</td>
            <td>{{ inspectionRow(3).ok }}</td>
            <td>{{ inspectionRow(3).ng }}</td>
            <td>{{ inspectionRow(3).qcWorker }}</td>
            <td>{{ inspectionRow(3).date }}</td>
            <td>{{ inspectionRow(3).defectReason }}</td>
            <td>{{ inspectionRow(3).returned }}</td>
            <td rowspan="2" class="vertical-label">报废</td>
            <td>来料</td>
            <td />
          </tr>
          <tr>
            <td />
            <th colspan="2">线检出</th>
            <td>{{ inspectionRow(4).label }}</td>
            <td>{{ inspectionRow(4).ok }}</td>
            <td>{{ inspectionRow(4).ng }}</td>
            <td>{{ inspectionRow(4).qcWorker }}</td>
            <td>{{ inspectionRow(4).date }}</td>
            <td>{{ inspectionRow(4).defectReason }}</td>
            <td>{{ inspectionRow(4).returned }}</td>
            <td>加工</td>
            <td />
          </tr>
          <tr>
            <th rowspan="2">QC确认</th>
            <th>出QC数</th>
            <th>核对员</th>
            <td>{{ inspectionRow(5).label }}</td>
            <td>{{ inspectionRow(5).ok }}</td>
            <td>{{ inspectionRow(5).ng }}</td>
            <td>{{ inspectionRow(5).qcWorker }}</td>
            <td>{{ inspectionRow(5).date }}</td>
            <td>{{ inspectionRow(5).defectReason }}</td>
            <td>{{ inspectionRow(5).returned }}</td>
            <td rowspan="2" class="vertical-label">允收数</td>
            <td rowspan="2" colspan="2" class="accepted-quantity">
              {{ item.status === 'closed' ? item.qualified_quantity : '' }}
            </td>
          </tr>
          <tr>
            <td />
            <td />
            <td>{{ inspectionRow(6).label }}</td>
            <td>{{ inspectionRow(6).ok }}</td>
            <td>{{ inspectionRow(6).ng }}</td>
            <td>{{ inspectionRow(6).qcWorker }}</td>
            <td>{{ inspectionRow(6).date }}</td>
            <td>{{ inspectionRow(6).defectReason }}</td>
            <td>{{ inspectionRow(6).returned }}</td>
          </tr>
        </tbody>
      </table>

      <footer>
        <span>领料人：{{ item.worker_name || '' }}</span>
        <span>QC主管确认：</span>
        <span>结单日期：</span>
        <span>制单人：董凤</span>
      </footer>
    </article>

    <template #footer>
      <ElButton @click="emit('update:modelValue', false)">关闭</ElButton>
      <ElButton type="primary" @click="print">打印</ElButton>
    </template>
  </ElDialog>
</template>

<style scoped>
.polish-print-sheet {
  page: polish-work-order;
  width: 272mm;
  max-width: none;
  box-sizing: border-box;
  margin: 0 auto;
  color: #000;
  background: #fff;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
  font-family: "SimSun", "Songti SC", serif;
  font-size: 16px;
}

h1 {
  margin: 0 0 12px;
  font-family: "SimHei", "Microsoft YaHei", sans-serif;
  font-size: 36px;
  line-height: 1.2;
  text-align: center;
}

.document-info {
  display: grid;
  grid-template-columns: 30% 48% 22%;
  font-size: 18px;
}

.document-info > div {
  display: flex;
  min-height: 34px;
  align-items: center;
  padding: 0 4px;
}

.document-info strong {
  flex: none;
  font-weight: 400;
}

.document-info span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.document-info .product-name {
  grid-column: 2;
}

.document-info .document-no {
  grid-column: 3;
  font-size: 15px;
}

.document-info .wide {
  grid-column: span 2;
}

.work-record {
  width: 100%;
  margin-top: 2px;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 15px;
}

.work-record col.col-a { width: 6%; }
.work-record col.col-b { width: 9%; }
.work-record col.col-c { width: 10%; }
.work-record col.col-d { width: 5.5%; }
.work-record col.col-e { width: 6.5%; }
.work-record col.col-f { width: 6.5%; }
.work-record col.col-g { width: 6.5%; }
.work-record col.col-h { width: 6%; }
.work-record col.col-i { width: 19%; }
.work-record col.col-j { width: 5%; }
.work-record col.col-k { width: 3.5%; }
.work-record col.col-l { width: 5.5%; }
.work-record col.col-m { width: 11%; }

.work-record th,
.work-record td {
  box-sizing: border-box;
  height: 43px;
  padding: 3px 4px;
  border: 1px solid #000;
  font-weight: 400;
  line-height: 1.15;
  text-align: center;
  vertical-align: middle;
}

.work-record .machine-row td,
.work-record .machine-row th {
  height: 34px;
}

.work-record .left {
  text-align: left;
}

.work-record .column-headings th {
  height: 45px;
}

.work-record .quantity {
  font-size: 24px;
  font-weight: 700;
}

.vertical-label {
  padding-inline: 8px;
  font-size: 17px;
  line-height: 1.25;
}

footer {
  display: grid;
  grid-template-columns: 1fr 1.3fr 1.1fr 1fr;
  gap: 20px;
  padding: 14px 4px 0;
  font-size: 17px;
}

@media screen and (max-width: 1180px) {
  :global(.polish-print-dialog .el-dialog__body) {
    overflow-x: auto;
  }
}

@media print {
  :global(body > *) {
    display: none !important;
  }

  :global(body > .polish-print-overlay--active) {
    display: block !important;
    position: static !important;
    width: auto !important;
    height: auto !important;
    overflow: visible !important;
    background: transparent !important;
  }

  :global(.polish-print-overlay .el-overlay-dialog) {
    position: static !important;
    overflow: visible !important;
  }

  .polish-print-sheet {
    position: static;
    width: 272mm;
    max-width: 272mm;
    margin: 0;
  }

  :global(.polish-print-dialog .el-dialog__header),
  :global(.polish-print-dialog .el-dialog__footer) {
    display: none !important;
  }

  :global(.polish-print-dialog.el-dialog) {
    width: auto !important;
    margin: 0 !important;
    padding: 0 !important;
    border: 0 !important;
    border-radius: 0 !important;
    background: #fff !important;
    box-shadow: none !important;
  }

  :global(.polish-print-dialog .el-dialog__body) {
    padding: 0 !important;
    overflow: visible !important;
  }
}

@page polish-work-order {
  size: A4 landscape;
  margin: 12mm;
}
</style>
