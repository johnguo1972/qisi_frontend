import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'
import { resolve } from 'path'

export default defineConfig({
  plugins: [uni()],
  resolve: {
    extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json', '.vue'],
    alias: [
      {
        find: '@',
        replacement: resolve(__dirname, 'src'),
      },
      {
        find: 'vue',
        replacement: resolve(__dirname, 'node_modules/@dcloudio/uni-h5-vue/dist/vue.runtime.esm.js'),
      },
      {
        find: 'vue/package.json',
        replacement: resolve(__dirname, 'node_modules/@dcloudio/uni-h5-vue/package.json'),
      },
    ]
  },
  define: {
    __UNI_FEATURE_PAGES__: 'true',
    __UNI_FEATURE_NAVIGATIONBAR__: 'true',
    __UNI_FEATURE_TABBAR__: 'true',
    __UNI_FEATURE_PULL_DOWN_REFRESH__: 'true',
    __UNI_FEATURE_RESPONSIVE__: 'true',
    __UNI_FEATURE_UNI_CLOUD__: 'false',
    __UNI_FEATURE_WX__: 'false',
    __UNI_FEATURE_WXS__: 'false',
    __UNI_FEATURE_LONGPRESS__: 'true',
    __UNI_FEATURE_ROUTER_MODE__: JSON.stringify('hash'),
    __UNI_FEATURE_NAVIGATIONBAR_BUTTONS__: 'false',
    __UNI_FEATURE_NAVIGATIONBAR_SEARCHINPUT__: 'false',
    __UNI_FEATURE_NAVIGATIONBAR_TRANSPARENT__: 'false',
    __UNI_FEATURE_LEFTWINDOW__: 'false',
    __UNI_FEATURE_RIGHTWINDOW__: 'false',
    __UNI_FEATURE_TOPWINDOW__: 'false',
    __UNI_FEATURE_TABBAR_MIDBUTTON__: 'false',
    __UNI_FEATURE_I__: 'false',
  },
  server: {
    port: 5173,
    headers: {
      'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://registry.npmmirror.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://registry.npmmirror.com; font-src 'self' https://cdn.jsdelivr.net https://registry.npmmirror.com data:; img-src 'self' data: blob: https:;",
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
      },
      '/media': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
