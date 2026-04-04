<script setup>
import {
  DataBoard,
  Lightning,
  TrendCharts,
  Reading,
  List,
  OfficeBuilding,
  Setting,
  Fold,
  Expand,
} from '@element-plus/icons-vue'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const collapsed = ref(false)
const asideWidth = computed(() => (collapsed.value ? '64px' : '220px'))

const active = computed(() => route.path)
</script>

<template>
  <el-container class="ems-shell">
    <el-aside class="ems-aside" :width="asideWidth">
      <div class="ems-brand">
        <span v-if="!collapsed" class="ems-brand-text">建筑能源 EMS</span>
        <span v-else class="ems-brand-mini">E</span>
      </div>
      <el-menu
        :default-active="active"
        :collapse="collapsed"
        router
        class="ems-menu"
        background-color="#0f172a"
        text-color="#94a3b8"
        active-text-color="#38bdf8"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/energy">
          <el-icon><Lightning /></el-icon>
          <span>能耗监测</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><TrendCharts /></el-icon>
          <span>统计分析</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Reading /></el-icon>
          <span>知识助手</span>
        </el-menu-item>
        <el-menu-item index="/incidents">
          <el-icon><List /></el-icon>
          <span>运维工单</span>
        </el-menu-item>
        <el-menu-item index="/twin">
          <el-icon><OfficeBuilding /></el-icon>
          <span>数字孪生</span>
        </el-menu-item>
        <el-menu-item index="/admin">
          <el-icon><Setting /></el-icon>
          <span>系统管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="ems-header">
        <div class="ems-header-left">
          <el-button text class="collapse-btn" @click="collapsed = !collapsed">
            <el-icon v-if="collapsed"><Expand /></el-icon>
            <el-icon v-else><Fold /></el-icon>
          </el-button>
          <span class="ems-breadcrumb">{{ route.meta?.title ?? '' }}</span>
        </div>
        <div class="ems-header-right">
          <span class="ems-env">Vue3 · Element Plus · ECharts</span>
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
  background: #f1f5f9;
}

.ems-aside {
  background: #0f172a;
  transition: width 0.2s ease;
  overflow: hidden;
}

.ems-brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}

.ems-brand-text {
  color: #f8fafc;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.02em;
}

.ems-brand-mini {
  color: #38bdf8;
  font-weight: 700;
  font-size: 18px;
}

.ems-menu {
  border-right: none;
}

.ems-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  padding: 0 16px;
  height: 56px;
}

.ems-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collapse-btn {
  font-size: 18px;
}

.ems-breadcrumb {
  color: #334155;
  font-weight: 500;
}

.ems-header-right {
  color: #64748b;
  font-size: 13px;
}

.ems-main {
  padding: 16px;
  overflow: auto;
}
</style>
