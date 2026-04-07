import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          meta: { title: '工作台' },
          component: () => import('@/views/DashboardView.vue'),
        },
        {
          path: 'energy',
          name: 'energy',
          meta: { title: '能耗监测' },
          component: () => import('@/views/EnergyView.vue'),
        },
        {
          path: 'stats',
          name: 'stats',
          meta: { title: '统计分析' },
          component: () => import('@/views/StatsView.vue'),
        },
        {
          path: 'knowledge',
          name: 'knowledge',
          meta: { title: '知识助手' },
          component: () => import('@/views/KnowledgeView.vue'),
        },
        {
          path: 'incidents',
          name: 'incidents',
          meta: { title: '运维工单' },
          component: () => import('@/views/IncidentsView.vue'),
        },
        {
          path: 'twin',
          name: 'twin',
          meta: { title: '数字孪生' },
          component: () => import('@/views/TwinView.vue'),
        },
        {
          path: 'admin',
          name: 'admin',
          meta: { title: '系统管理' },
          component: () => import('@/views/AdminView.vue'),
        },
      ],
    },
  ],
})

export default router
