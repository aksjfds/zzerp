<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

type ModuleItem = {
  title: string
  description: string
  badge: string
  accent: string
  path?: string
}

type TodoItem = {
  title: string
  source: string
  count: number
}

const menuGroups = [
  {
    title: '业务中心',
    items: ['销售管理', '采购管理', '库存管理', '生产计划'],
  },
  {
    title: '经营管理',
    items: ['财务管理', '客户管理', '供应商管理', '报表中心'],
  },
  {
    title: '系统配置',
    items: ['组织架构', '权限角色', '基础资料', '审批流程'],
  },
]

const moduleItems: ModuleItem[] = [
  {
    title: '销售管理',
    description: '报价、订单、出库和回款跟踪',
    badge: '12 单待处理',
    accent: '#2563eb',
  },
  {
    title: '采购管理',
    description: '请购、采购订单、到货和对账',
    badge: '8 单待确认',
    accent: '#059669',
  },
  {
    title: '库存管理',
    description: '入库、出库、调拨、盘点和预警',
    badge: '5 项预警',
    accent: '#d97706',
  },
  {
    title: '财务管理',
    description: '应收应付、发票、费用和结算',
    badge: '18 笔待审核',
    accent: '#7c3aed',
  },
  {
    title: '生产计划',
    description: '工单、物料需求和产能排程',
    badge: '3 个延误风险',
    accent: '#dc2626',
    path: '/production-plan',
  },
  {
    title: '报表中心',
    description: '经营看板、库存周转和利润分析',
    badge: '今日已更新',
    accent: '#0891b2',
  },
]

const todoItems: TodoItem[] = [
  { title: '销售订单审批', source: '来自销售管理', count: 7 },
  { title: '采购价格复核', source: '来自采购管理', count: 4 },
  { title: '库存低水位补货', source: '来自库存管理', count: 5 },
  { title: '费用报销审核', source: '来自财务管理', count: 2 },
]

const metrics = [
  { label: '今日订单', value: '128', trend: '+16.2%' },
  { label: '库存预警', value: '24', trend: '-3 项' },
  { label: '待审批', value: '31', trend: '+5' },
  { label: '本月回款', value: '286.4万', trend: '+9.8%' },
]

const activeScope = ref('全部')
const router = useRouter()

function openModule(item: ModuleItem) {
  if (item.path) {
    router.push(item.path)
  }
}
</script>

<template>
  <ElContainer class="erp-shell">
    <ElAside class="erp-aside" width="248px">
      <div class="brand">
        <div class="brand-mark">ZZ</div>
        <div>
          <div class="brand-name">ZZ ERP</div>
          <div class="brand-subtitle">企业资源计划系统</div>
        </div>
      </div>

      <ElScrollbar class="menu-scroll">
        <section v-for="group in menuGroups" :key="group.title" class="menu-group">
          <div class="menu-title">{{ group.title }}</div>
          <ElMenu class="module-menu" default-active="销售管理">
            <ElMenuItem v-for="item in group.items" :key="item" :index="item">
              <span>{{ item }}</span>
            </ElMenuItem>
          </ElMenu>
        </section>
      </ElScrollbar>
    </ElAside>

    <ElContainer>
      <ElHeader class="erp-header" height="64px">
        <div>
          <div class="page-title">业务导航</div>
          <div class="page-subtitle">统一入口、待办处理、经营状态总览</div>
        </div>
        <div class="header-actions">
          <ElTag type="success" effect="light">演示账套</ElTag>
          <ElButton>切换组织</ElButton>
          <ElButton type="primary">新建单据</ElButton>
        </div>
      </ElHeader>

      <ElMain class="erp-main">
        <section class="hero-band">
          <div class="hero-copy">
            <div class="hero-kicker">ERP Console</div>
            <h1>从流程入口开始处理今天的业务</h1>
            <p>销售、采购、库存、财务和生产数据集中在一个工作台，后续可直接接入权限菜单与业务接口。</p>
          </div>
          <div class="hero-actions">
            <ElButton type="primary" size="large">查看待办</ElButton>
            <ElButton size="large">经营报表</ElButton>
          </div>
        </section>

        <section class="metrics-grid">
          <div v-for="metric in metrics" :key="metric.label" class="metric-panel">
            <div class="metric-label">{{ metric.label }}</div>
            <div class="metric-value">{{ metric.value }}</div>
            <div class="metric-trend">{{ metric.trend }}</div>
          </div>
        </section>

        <section class="content-grid">
          <div class="module-section">
            <div class="section-heading">
              <div>
                <h2>常用业务入口</h2>
                <p>覆盖 ERP 核心链路，后续可绑定权限和动态菜单</p>
              </div>
              <ElSegmented v-model="activeScope" :options="['全部', '业务', '管理']" />
            </div>

            <div class="module-grid">
              <ElCard v-for="item in moduleItems" :key="item.title" shadow="hover" class="module-card">
                <div class="module-accent" :style="{ backgroundColor: item.accent }"></div>
                <div class="module-card-head">
                  <h3>{{ item.title }}</h3>
                  <ElTag size="small" effect="plain">{{ item.badge }}</ElTag>
                </div>
                <p>{{ item.description }}</p>
                <div class="module-actions">
                  <ElButton type="primary" plain @click="openModule(item)">进入模块</ElButton>
                  <ElButton text>查看报表</ElButton>
                </div>
              </ElCard>
            </div>
          </div>

          <aside class="side-panel">
            <section class="todo-panel">
              <div class="section-heading compact">
                <h2>待办中心</h2>
                <ElButton text>全部</ElButton>
              </div>
              <div class="todo-list">
                <div v-for="todo in todoItems" :key="todo.title" class="todo-item">
                  <div>
                    <div class="todo-title">{{ todo.title }}</div>
                    <div class="todo-source">{{ todo.source }}</div>
                  </div>
                  <ElBadge :value="todo.count" type="primary" />
                </div>
              </div>
            </section>

            <section class="notice-panel">
              <h2>经营提醒</h2>
              <ElTimeline>
                <ElTimelineItem timestamp="09:30">库存周转率低于目标，需要关注呆滞料。</ElTimelineItem>
                <ElTimelineItem timestamp="11:00">3 个重点客户应收账期即将到期。</ElTimelineItem>
                <ElTimelineItem timestamp="15:20">本周采购到货及时率为 96.8%。</ElTimelineItem>
              </ElTimeline>
            </section>
          </aside>
        </section>
      </ElMain>
    </ElContainer>
  </ElContainer>
</template>

<style scoped>
.erp-shell {
  min-height: 100vh;
  background:
    linear-gradient(180deg, #f7fafc 0, #eef2f7 280px, #edf1f5 100%);
}

.erp-aside {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #dce3ec;
  background: #172033;
  color: #ffffff;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 64px;
  padding: 0 20px;
  border-bottom: 1px solid rgb(255 255 255 / 10%);
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  place-items: center;
  border-radius: 8px;
  background: linear-gradient(135deg, #2563eb, #14b8a6);
  font-size: 13px;
  font-weight: 700;
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
}

.brand-subtitle {
  margin-top: 2px;
  color: #aeb8c7;
  font-size: 12px;
}

.menu-scroll {
  flex: 1;
}

.menu-group {
  padding: 16px 12px 0;
}

.menu-title {
  padding: 0 8px 8px;
  color: #8fa0b6;
  font-size: 12px;
}

.module-menu {
  border-right: 0;
  background: transparent;
}

.module-menu :deep(.el-menu-item) {
  height: 40px;
  margin-bottom: 4px;
  border-radius: 6px;
  color: #d8e1ee;
}

.module-menu :deep(.el-menu-item:hover),
.module-menu :deep(.el-menu-item.is-active) {
  background: rgb(37 99 235 / 20%);
  color: #ffffff;
}

.erp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #dfe6ef;
  background: rgb(255 255 255 / 88%);
  backdrop-filter: blur(12px);
}

.page-title {
  font-size: 18px;
  font-weight: 700;
}

.page-subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.erp-main {
  padding: 20px;
}

.hero-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 178px;
  margin-bottom: 18px;
  padding: 28px 32px;
  overflow: hidden;
  border: 1px solid #dbe5ef;
  border-radius: 8px;
  background:
    linear-gradient(135deg, rgb(21 92 178 / 94%), rgb(15 118 110 / 90%)),
    linear-gradient(90deg, #155cb2, #0f766e);
  color: #ffffff;
  box-shadow: 0 18px 36px rgb(15 23 42 / 10%);
}

.hero-copy {
  max-width: 680px;
}

.hero-kicker {
  color: #bfdbfe;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.hero-copy h1 {
  margin: 8px 0 10px;
  font-size: 30px;
  line-height: 1.25;
}

.hero-copy p {
  margin: 0;
  color: #e5f2ff;
  font-size: 14px;
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.hero-actions :deep(.el-button:not(.el-button--primary)) {
  border-color: rgb(255 255 255 / 70%);
  background: rgb(255 255 255 / 14%);
  color: #ffffff;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.metric-panel,
.todo-panel,
.notice-panel {
  border: 1px solid #dfe6ef;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgb(15 23 42 / 5%);
}

.metric-panel {
  padding: 18px;
}

.metric-label {
  color: #64748b;
  font-size: 13px;
}

.metric-value {
  margin-top: 8px;
  color: #0f172a;
  font-size: 28px;
  font-weight: 700;
}

.metric-trend {
  margin-top: 6px;
  color: #0f766e;
  font-size: 13px;
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 18px;
  align-items: start;
}

.module-section {
  min-width: 0;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-heading h2,
.todo-panel h2,
.notice-panel h2 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.section-heading p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.section-heading.compact {
  margin-bottom: 0;
  padding: 16px 16px 0;
}

.module-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.module-card {
  position: relative;
  overflow: hidden;
  min-height: 172px;
  border-radius: 8px;
  border-color: #dfe6ef;
  box-shadow: 0 10px 24px rgb(15 23 42 / 5%);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.module-card:hover {
  border-color: #b8c7d9;
  box-shadow: 0 18px 34px rgb(15 23 42 / 10%);
  transform: translateY(-2px);
}

.module-accent {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
}

.module-card-head {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  justify-content: space-between;
}

.module-card h3 {
  margin: 0;
  color: #0f172a;
  font-size: 17px;
}

.module-card p {
  min-height: 44px;
  margin: 12px 0 18px;
  color: #64748b;
  line-height: 1.55;
}

.module-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.side-panel {
  display: grid;
  gap: 16px;
}

.todo-list {
  padding: 8px 16px 16px;
}

.todo-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #edf1f5;
}

.todo-item:last-child {
  border-bottom: 0;
}

.todo-title {
  color: #0f172a;
  font-weight: 600;
}

.todo-source {
  margin-top: 4px;
  color: #7b8794;
  font-size: 12px;
}

.notice-panel {
  padding: 16px 16px 4px;
}

.notice-panel h2 {
  margin-bottom: 14px;
}

@media (max-width: 1180px) {
  .metrics-grid,
  .module-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .erp-shell {
    display: block;
  }

  .erp-aside {
    width: 100% !important;
    min-height: auto;
  }

  .erp-header {
    height: auto;
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 16px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .hero-band {
    flex-direction: column;
    align-items: flex-start;
    padding: 22px;
  }

  .hero-copy h1 {
    font-size: 24px;
  }

  .hero-actions {
    width: 100%;
    margin-top: 18px;
    flex-wrap: wrap;
  }

  .metrics-grid,
  .module-grid {
    grid-template-columns: 1fr;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
}
</style>
