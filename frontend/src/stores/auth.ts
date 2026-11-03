import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/services/api'
import router from '@/router'

interface AuthUser {
  [key: string]: any
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token') || null)
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token') || null)
  const loading = ref<boolean>(false)
  const offersCount = ref<number>(parseInt(sessionStorage.getItem('offers_count') || '0', 10) || 0)
  const discontinuedCount = ref<number>(parseInt(sessionStorage.getItem('discontinued_count') || '0', 10) || 0)
  const lastLoginAt = ref<number>(parseInt(sessionStorage.getItem('last_login_at') || '0', 10) || 0)
  let keepAliveInterval: ReturnType<typeof setInterval> | null = null

  const isAuthenticated = computed(() => {
    return !!accessToken.value && !!user.value
  })

  const isStaff = computed(() => {
    return isAuthenticated.value && !!user.value?.is_staff
  })

  const login = async (username: string, password: string) => {
    loading.value = true
    try {
      const response = await api.post('/api/token/', {
        username,
        password,
      })

      const access = response.data.access
      const refresh = response.data.refresh
      const userData = response.data.user
      const sessionId = response.data.session_id

      setTokens(access, refresh)
      setUser(userData)
      try { localStorage.setItem('session_id', sessionId) } catch (e) {}

      startKeepAlive()

      try {
        sessionStorage.removeItem('view_logged_oferta')
        sessionStorage.removeItem('view_logged_discontinuado')
      } catch (e) {}

      const [offersRes, discontinuedRes] = await Promise.allSettled([
        api.get('/api/articulos/', { params: { oferta: 1, page_size: 1 } }),
        api.get('/api/articulos/', { params: { discontinuados: 1, page_size: 1 } })
      ])

      if (offersRes.status === 'fulfilled') {
        const offersTotal = offersRes.value.data?.count || 0
        offersCount.value = offersTotal
        try { sessionStorage.setItem('offers_count', String(offersTotal)) } catch (e) {}
      } else {
        console.warn('No se pudo consultar ofertas tras login:', offersRes.reason)
      }

      if (discontinuedRes.status === 'fulfilled') {
        const discontinuedTotal = discontinuedRes.value.data?.count || 0
        discontinuedCount.value = discontinuedTotal
        try { sessionStorage.setItem('discontinued_count', String(discontinuedTotal)) } catch (e) {}
      } else {
        console.warn('No se pudo consultar discontinuados tras login:', discontinuedRes.reason)
      }

      lastLoginAt.value = Date.now()
      try { sessionStorage.setItem('last_login_at', String(lastLoginAt.value)) } catch (e) {}

      try { window.dispatchEvent(new Event('user-logged-in')) } catch (e) { /* ignore */ }

      router.push('/dashboard')
    } catch (error) {
      throw error
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    const sessionId = localStorage.getItem('session_id')

    try {
      await api.post('/api/logout/', { session_id: sessionId })
    } catch (error) {
      console.warn('No se pudo registrar el cierre de sesión:', error)
    } finally {
      stopKeepAlive()

      accessToken.value = null
      refreshToken.value = null
      user.value = null

      try {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user')
        localStorage.removeItem('session_id')
      } catch (e) {}

      window.dispatchEvent(new Event('user-logged-out'))

      router.push('/login')
    }
  }

  const startKeepAlive = () => {
    stopKeepAlive()

    keepAliveInterval = setInterval(async () => {
      if (isAuthenticated.value) {
        try {
          await api.post('/api/keep-alive/')
        } catch (error) {
          console.warn('Error en keep-alive:', error)
        }
      }
    }, 10 * 60 * 1000)
  }

  const stopKeepAlive = () => {
    if (keepAliveInterval) {
      clearInterval(keepAliveInterval as unknown as number)
      keepAliveInterval = null
    }
  }

  const setUser = (userData: AuthUser | null) => {
    user.value = userData
    try { localStorage.setItem('user', JSON.stringify(userData)) } catch (e) {}
  }

  const setTokens = (access: string | null, refresh: string | null) => {
    accessToken.value = access
    refreshToken.value = refresh
    try {
      if (access) localStorage.setItem('access_token', access)
      else localStorage.removeItem('access_token')
      if (refresh) localStorage.setItem('refresh_token', refresh)
      else localStorage.removeItem('refresh_token')
    } catch (e) {}
  }

  const initializeFromStorage = () => {
    const savedUser = localStorage.getItem('user')
    const savedAccessToken = localStorage.getItem('access_token')
    const savedRefreshToken = localStorage.getItem('refresh_token')
    
    if (savedUser && savedAccessToken) {
      try {
        user.value = JSON.parse(savedUser)
        accessToken.value = savedAccessToken
        refreshToken.value = savedRefreshToken
        console.log('Session restored from localStorage:', {
          user: user.value?.username,
          hasToken: !!accessToken.value
        })
      } catch (error) {
        console.error('Error parsing saved user data:', error)
        try {
          localStorage.removeItem('user')
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
        } catch (e) {}
      }
    }
  }

  initializeFromStorage()

  return {
    user,
    accessToken,
    refreshToken,
    loading,
    offersCount,
    discontinuedCount,
    lastLoginAt,
    isAuthenticated,
    isStaff,
    login,
    logout,
    setUser,
    setTokens,
    initializeFromStorage,
  }
})
