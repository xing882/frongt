<script setup>
import {
  DataBoard,
  Lightning,
  Histogram,
  Reading,
  List,
  Fold,
  Expand,
  Cpu,
  MoreFilled,
  Monitor,
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)
const asideWidth = computed(() => (collapsed.value ? '64px' : '228px'))
const active = computed(() => route.path)

const openeds = ref(['grp-analysis', 'grp-more'])
</script>

<template>
  <el-container class="ems-shell">
    <el-aside class="ems-aside" :width="asideWidth">
      <div class="ems-brand">
        <div v-if="!collapsed" class="ems-brand-full">
          <span class="ems-brand-mark">EMS</span>
          <div class="ems-brand-text">
            <div class="ems-brand-title">建筑能源</div>
            <div class="ems-brand-sub">Energy Management</div>
          </div>
        </div>
        <span v-else class="ems-brand-mini">E</span>
      </div>

      <el-scrollbar class="ems-menu-wrap">
        <el-menu
          :default-active="active"
          :default-openeds="openeds"
          :collapse="collapsed"
          router
          class="ems-menu"
          background-color="transparent"
          text-color="rgba(255,255,255,0.72)"
          active-text-color="#ffffff"
        >
          <el-menu-item index="/dashboard">
            <el-icon><DataBoard /></el-icon>
            <span class="menu-label">能源仪表盘</span>
          </el-menu-item>

          <el-menu-item index="/screen">
            <el-icon><Monitor /></el-icon>
            <span class="menu-label">数据大屏</span>
          </el-menu-item>

          <el-menu-item index="/energy">
            <el-icon><Lightning /></el-icon>
            <span class="menu-label">能源监控</span>
          </el-menu-item>

          <el-sub-menu index="grp-analysis">
            <template #title>
              <el-icon><Histogram /></el-icon>
              <span class="menu-label">数据分析</span>
            </template>
            <el-menu-item index="/stats">
              <span class="sub-label">统计分析</span>
            </el-menu-item>
            <el-menu-item index="/benchmark">
              <span class="sub-label">能效对标</span>
            </el-menu-item>
          </el-sub-menu>

          <el-menu-item index="/knowledge">
            <el-icon><Reading /></el-icon>
            <span class="menu-label">知识检索</span>
          </el-menu-item>

          <el-menu-item index="/incidents">
            <el-icon><List /></el-icon>
            <span class="menu-label">告警与工单</span>
          </el-menu-item>

          <el-sub-menu index="grp-more">
            <template #title>
              <el-icon><MoreFilled /></el-icon>
              <span class="menu-label">更多</span>
            </template>
            <el-menu-item index="/twin">
              <span class="sub-label">孪生与视觉</span>
            </el-menu-item>
            <el-menu-item index="/operations">
              <span class="sub-label">运营与预测</span>
            </el-menu-item>
            <el-menu-item index="/admin">
              <span class="sub-label">系统管理</span>
            </el-menu-item>
          </el-sub-menu>
        </el-menu>
      </el-scrollbar>

      <div class="ems-aside-foot">
        <el-icon class="foot-icon"><Cpu /></el-icon>
        <span v-if="!collapsed" class="foot-text">折叠侧栏以扩大内容区</span>
      </div>
    </el-aside>

    <el-container class="ems-right">
      <el-header class="ems-header">
        <div class="ems-header-left">
          <el-tooltip content="展开 / 收起导航" placement="bottom">
            <el-button text class="collapse-btn" aria-label="切换侧栏" @click="collapsed = !collapsed">
              <el-icon v-if="collapsed"><Expand /></el-icon>
              <el-icon v-else><Fold /></el-icon>
            </el-button>
          </el-tooltip>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>建筑能源 EMS</el-breadcrumb-item>
            <el-breadcrumb-item>{{ route.meta?.title ?? '' }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="ems-header-right">
          <el-tag class="hide-xs" type="info" size="small" effect="plain">REST /api</el-tag>
        </div>
      </el-header>
      <el-main class="ems-main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.ems-shell {
  min-height: 100vh;
  background: var(--ems-main-bg, #f5f7fa);
}

.ems-aside {
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #3d4f5f 0%, #2f3d4a 100%);
  transition: width 0.2s ease;
  overflow: hidden;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
}

.ems-brand {
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0 12px;
}

.ems-brand-full {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.ems-brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(145deg, #5b7c9c, #3d5a78);
  color: #fff;
  font-weight: 800;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ems-brand-text {
  flex: 1;
  min-width: 0;
}

.ems-brand-title {
  color: #fff;
  font-weight: 600;
  font-size: 15px;
  line-height: 1.2;
}

.ems-brand-sub {
  color: rgba(255, 255, 255, 0.5);
  font-size: 11px;
  margin-top: 2px;
}

.ems-brand-mini {
  color: #8cc8ff;
  font-weight: 800;
  font-size: 18px;
}

.ems-menu-wrap {
  flex: 1;
  min-height: 0;
}

.ems-menu {
  border-right: none;
  padding: 8px 0 16px;
}

.menu-label {
  font-weight: 500;
}

.sub-label {
  font-weight: 400;
}

.sub-ico {
  margin-right: 4px;
  font-size: 15px;
  vertical-align: middle;
}

.ems-menu :deep(.el-sub-menu__title),
.ems-menu :deep(.el-menu-item) {
  margin: 3px 10px;
  border-radius: 6px;
}

/* 选中项：背景 + 加粗 */
.ems-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(24, 144, 255, 0.95), rgba(83, 163, 216, 0.85)) !important;
  color: #fff !important;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.ems-menu :deep(.el-menu-item.is-active .menu-label),
.ems-menu :deep(.el-menu-item.is-active .sub-label) {
  font-weight: 600;
}

.ems-menu :deep(.el-menu-item:not(.is-active):hover) {
  background: rgba(255, 255, 255, 0.08) !important;
}

.ems-menu :deep(.el-sub-menu .el-menu-item) {
  min-width: auto;
  padding-left: 44px !important;
}

.ems-menu :deep(.el-sub-menu__title:hover) {
  background: rgba(255, 255, 255, 0.06) !important;
}

.ems-aside-foot {
  flex-shrink: 0;
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 11px;
}

.foot-icon {
  font-size: 16px;
}

.foot-text {
  line-height: 1.3;
}

.ems-right {
  min-width: 0;
}

.ems-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 0 16px;
  height: 56px;
}

.ems-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.collapse-btn {
  font-size: 18px;
  color: rgba(0, 0, 0, 0.65);
}

.ems-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.ems-main {
  padding: 16px;
  overflow: auto;
  background: var(--ems-main-bg, #f5f7fa);
}

@media (max-width: 768px) {
  .ems-main {
    padding: 12px;
  }

  .hide-xs {
    display: none;
  }

  .ems-header {
    height: auto;
    min-height: 48px;
    flex-wrap: wrap;
    padding-top: 8px;
    padding-bottom: 8px;
  }

  .ems-aside {
    box-shadow: none;
  }
}
</style>
