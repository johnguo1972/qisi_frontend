import { defineConfig } from 'vitest/config'
import uni from '@dcloudio/vite-plugin-uni'
import { resolve } from 'path'
import * as compiler from 'vue/compiler-sfc'

export default defineConfig({
  plugins: [uni({ vueOptions: { compiler } })],
  resolve: {
    alias: [
      { find: '@', replacement: resolve(__dirname, 'src') },
      { find: '@vue/test-utils', replacement: resolve(__dirname, 'node_modules/@vue/test-utils/dist/vue-test-utils.esm-bundler.mjs') },
      { find: 'vue', replacement: resolve(__dirname, 'node_modules/@dcloudio/uni-h5-vue/dist/vue.runtime.esm.js') },
      { find: 'vue/package.json', replacement: resolve(__dirname, 'node_modules/@dcloudio/uni-h5-vue/package.json') },
    ],
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    server: {
      deps: {
        inline: ['@vue/test-utils'],
      },
    },
  },
})
