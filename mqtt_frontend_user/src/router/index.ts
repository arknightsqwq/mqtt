import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/auth/Login.vue'),
      meta: { title: '登录', guest: true }
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/auth/Register.vue'),
      meta: { title: '注册', guest: true }
    },
    {
      path: '/',
      component: () => import('@/views/main/MainLayout.vue'),
      redirect: '/devices',
      children: [
        {
          path: 'devices',
          name: 'DevicesHome',
          component: () => import('@/views/main/DevicesHome.vue'),
          meta: { title: '我的设备' }
        },
        {
          path: 'alerts',
          name: 'AlertsList',
          component: () => import('@/views/main/AlertsList.vue'),
          meta: { title: '告警中心' }
        },
        {
          path: 'profile',
          name: 'Profile',
          component: () => import('@/views/main/Profile.vue'),
          meta: { title: '个人中心' }
        },
        {
          path: 'device/:id',
          name: 'DeviceDetail',
          component: () => import('@/views/device/DeviceDetail.vue'),
          meta: { title: '设备详情' }
        }
      ]
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/devices'
    }
  ]
})

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'IoT 设备管家'} | IoT 设备管家`
  const token = localStorage.getItem('user_token')

  if (to.meta.guest) {
    // 已登录用户访问登录/注册页 → 跳转设备页
    token ? next('/devices') : next()
  } else if (!token) {
    // 未登录 → 跳转登录页（保留目标路径）
    next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
  } else {
    next()
  }
})

export default router
