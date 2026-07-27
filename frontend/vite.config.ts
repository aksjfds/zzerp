import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

// https://vite.dev/config/
export default defineConfig({
  server: { host: '0.0.0.0' },
  preview: { host: '0.0.0.0' },
  plugins: [
    vue(),
    vueDevTools(),
    
    AutoImport({
      resolvers: [ElementPlusResolver()],
    }),
    Components({
      resolvers: [ElementPlusResolver()],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20 * 1024,
          maxSize: 350 * 1024,
          groups: [
            {
              name: 'logicflow',
              test: /node_modules[\\/]@logicflow[\\/]/,
              priority: 40,
            },
            {
              name: 'vue',
              test: /node_modules[\\/](?:vue|vue-router|pinia|@vue)[\\/]/,
              priority: 30,
            },
            {
              name: 'element-plus',
              test: /node_modules[\\/](?:element-plus|@element-plus)[\\/]/,
              priority: 20,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              priority: 10,
              entriesAware: true,
              entriesAwareMergeThreshold: 20 * 1024,
            },
          ],
        },
      },
    },
  },
})
