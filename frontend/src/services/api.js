// src/services/api.js
import axios from 'axios'
// avoid static import of the auth store to prevent circular dependency
// auth store imports this module (api), so using a dynamic import inside
// interceptors avoids issues where the store isn't fully initialized yet.

const API_BASE_URL = import.meta.env.PROD
  ? '/' // Use relative path in production
  : 'http://192.168.0.200:8000/'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

let isRefreshing = false
let failedQueue = []

const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) prom.reject(error)
    else prom.resolve(token)
  })
  failedQueue = []
}

api.interceptors.request.use(
  // make the interceptor async and import the store lazily to avoid
  // circular import problems
  async (config) => {
    try {
      const module = await import('@/stores/auth')
      const authStore = module.useAuthStore()
      const token = authStore.accessToken?.value ?? authStore.accessToken
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    } catch (err) {
      // If import or store access fails, continue without token
      console.warn('Could not access auth store in request interceptor:', err)
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    let authStore = null
    try {
      const module = await import('@/stores/auth')
      authStore = module.useAuthStore()
    } catch (err) {
      console.warn('Could not access auth store in response interceptor:', err)
    }

    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest._skipAuthRefresh) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        }).catch(err => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = authStore?.refreshToken?.value ?? authStore?.refreshToken
      if (!refreshToken) {
        // No refresh token available - clear auth and redirect to login
        await clearAuthAndRedirect(authStore)
        return Promise.reject(error)
      }

      try {
        // Mark this request to skip the interceptor to avoid infinite loop
        const response = await axios.post(API_BASE_URL + 'api/token/refresh/', {
          refresh: refreshToken,
        }, {
          _skipAuthRefresh: true // flag to prevent interceptor from running
        })

        const newAccessToken = response.data.access
        const currentRefresh = authStore?.refreshToken?.value ?? authStore?.refreshToken
        authStore.setTokens(newAccessToken, currentRefresh)

        api.defaults.headers.common.Authorization = `Bearer ${newAccessToken}`
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`

        processQueue(null, newAccessToken)
        return api(originalRequest)
      } catch (refreshError) {
        // If refresh fails, clear auth and redirect to login
        processQueue(refreshError, null)
        await clearAuthAndRedirect(authStore)
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// Helper function to clear authentication and redirect to login
async function clearAuthAndRedirect(authStore) {
  console.log('🔴 Session expired - clearing auth and redirecting to login')
  
  // Clear localStorage directly first
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user')
  localStorage.removeItem('session_id')
  window.dispatchEvent(new Event('user-logged-out'))
  
  // Update store state if available (without calling the logout endpoint)
  try {
    if (authStore) {
      if (authStore.accessToken?.value !== undefined) authStore.accessToken.value = null
      else authStore.accessToken = null
      if (authStore.refreshToken?.value !== undefined) authStore.refreshToken.value = null
      else authStore.refreshToken = null
      if (authStore.user?.value !== undefined) authStore.user.value = null
      else authStore.user = null
    }
  } catch (e) {
    console.warn('Could not update store state:', e)
  }
  
  // Direct redirect to login
  if (window.location.pathname !== '/login') {
    try {
      const routerModule = await import('@/router')
      const router = routerModule.default
      await router.push('/login')
    } catch (e) {
      console.warn('Could not use router, redirecting via window.location:', e)
      window.location.href = '/login'
    }
  }
}

export default api
