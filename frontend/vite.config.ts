import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'logo.png'],
        manifest: {
          name: 'Ferretería Avenida SA - Portal de ventas',
          short_name: 'FerretAvenida',
          description: 'Portal de ventas de Ferretería Avenida SA',
          theme_color: '#1f2937',
          background_color: '#ffffff',
          display: 'standalone',
          orientation: 'portrait-primary',
          scope: '/',
          start_url: '/',
          categories: ['business', 'productivity'],
          lang: 'es',
          icons: [
            { src: 'pwa-64x64.svg', sizes: '64x64', type: 'image/svg+xml' },
            { src: 'pwa-192x192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'any' },
            { src: 'pwa-512x512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' },
            { src: 'favicon.ico', sizes: '16x16 32x32 48x48', type: 'image/x-icon' }
          ]
        },

        workbox: {
          cleanupOutdatedCaches: true,
          clientsClaim: true,
          skipWaiting: true,
          globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
          // El service worker sirve el index.html de la SPA en TODA navegacion
          // (NavigationRoute). Eso tapaba el admin de Django (/admin/) y el
          // health check (/health/): la navegacion devolvia la SPA en vez de ir
          // al backend. Con el denylist, esas rutas van a la red.
          navigateFallbackDenylist: [/^\/admin\//, /^\/health\//],
          runtimeCaching: [
            {
              urlPattern: ({ url }: any) => url.pathname.startsWith('/informes/'),
              handler: 'NetworkOnly',
              options: { cacheName: 'no-cache-informes' }
            },
            {
              // El admin de Django y el health check van siempre a la red:
              // el admin no tiene nada que ver con la SPA y el health check
              // no puede servir un JSON viejo desde el cache.
              urlPattern: ({ url }: any) =>
                url.pathname.startsWith('/admin/') || url.pathname === '/health/',
              handler: 'NetworkOnly',
              options: { cacheName: 'no-cache-backend' }
            },
            {
              urlPattern: ({ url }: any) => url.origin === self.origin,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'html-cache',
                expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 }
              }
            }
          ]
        },

        devOptions: { enabled: true }
      })
    ],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src')
      }
    },

    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-vue': ['vue', 'vue-router', 'pinia'],
            'vendor-charts': ['apexcharts', 'vue3-apexcharts'],
            'vendor-utils': ['axios', 'sweetalert2'],
            'vendor-excel': ['xlsx'],
            'vendor-ui': ['@heroicons/vue']
          },
          chunkFileNames: (chunkInfo) => {
            if (chunkInfo.name === 'vendor-vue') return 'assets/vue-[hash].js'
            if (chunkInfo.name === 'vendor-charts') return 'assets/charts-[hash].js'
            if (chunkInfo.name === 'vendor-utils') return 'assets/utils-[hash].js'
            if (chunkInfo.name === 'vendor-excel') return 'assets/excel-[hash].js'
            if (chunkInfo.name === 'vendor-ui') return 'assets/ui-[hash].js'
            return 'assets/[name]-[hash].js'
          }
        }
      },
      chunkSizeWarningLimit: 600,
      minify: 'terser',
      terserOptions: { compress: { drop_console: true, drop_debugger: true } }
    },

    server: {
      host: '0.0.0.0',
      strictPort: false,
      watch: { usePolling: true, interval: 1000 }
    }
  }
})
