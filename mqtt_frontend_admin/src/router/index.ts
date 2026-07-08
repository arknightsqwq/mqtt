import { createRouter, createWebHistory } from 'vue-router'
import { STORAGE_KEYS } from '@/constants/storage'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { title: '管理员登录' } },
    {
      path: '/admin', name: 'Layout', component: () => import('@/views/Layout.vue'),
      redirect: '/admin/dashboard',
      children: [
        { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue'), meta: { title: '管理首页' } },
        { path: 'devices', name: 'DeviceList', component: () => import('@/views/DeviceList.vue'), meta: { title: '设备管理' } },
        { path: 'register-device', name: 'DeviceRegister', component: () => import('@/views/DeviceRegister.vue'), meta: { title: '注册设备' } },
        { path: 'users', name: 'UserList', component: () => import('@/views/UserList.vue'), meta: { title: '用户管理' } },
        { path: 'create-user', name: 'UserCreate', component: () => import('@/views/UserCreate.vue'), meta: { title: '创建用户' } },
        { path: 'messages', name: 'MessageViewer', component: () => import('@/views/MessageViewer.vue'), meta: { title: '消息查询' } },
        { path: 'logs', name: 'LogViewer', component: () => import('@/views/LogViewer.vue'), meta: { title: '操作日志' } },
      ],
    },
  ],
})

router.beforeEach((to, _from, next) => {
  document.title = (to.meta.title as string) || 'IoT 管理后台'
  const pub = ['/login']; const t = sessionStorage.getItem(STORAGE_KEYS.ADMIN_TOKEN)
  if (!t && !pub.includes(to.path)) next('/login')
  else if (t && pub.includes(to.path)) next('/admin')
  else next()
})

export default router
