import { createApp } from 'vue'; import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'; import * as Icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'; import App from './App.vue'; import router from './router'

const app = createApp(App)
for (const [k, c] of Object.entries(Icons)) app.component(k, c)
app.use(createPinia()); app.use(router); app.use(ElementPlus)
app.mount('#app')
