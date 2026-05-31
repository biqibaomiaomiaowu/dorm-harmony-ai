import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }

    if (to.fullPath !== from.fullPath) {
      return { top: 0 }
    }
  },
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/record',
      name: 'record',
      component: () => import('@/views/RecordView.vue'),
    },
    {
      path: '/analysis',
      name: 'analysis',
      component: () => import('@/views/AnalysisView.vue'),
    },
    {
      path: '/archive',
      name: 'archive',
      component: () => import('@/views/EventArchiveView.vue'),
    },
    {
      path: '/rehearsal',
      name: 'rehearsal',
      component: () => import('@/views/RehearsalHomeView.vue'),
    },
    {
      path: '/rehearsal/scenario',
      name: 'scenario-training',
      component: () => import('@/views/ScenarioTrainingView.vue'),
    },
    {
      path: '/rehearsal/custom',
      name: 'custom-rehearsal',
      component: () => import('@/views/SimulationView.vue'),
    },
    {
      path: '/simulate',
      name: 'simulate',
      redirect: (to) => ({ name: 'custom-rehearsal', query: to.query }),
    },
    {
      path: '/review',
      name: 'review',
      component: () => import('@/views/ReviewView.vue'),
    },
  ],
})

export default router
