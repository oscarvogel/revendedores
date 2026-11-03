// stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'
import router from '../router'

export const useAuthStore = defineStore('auth', () => {
  // Estado
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || null)
  const refreshToken = ref(localStorage.getItem('refresh_token') || null)
  const loading = ref(false)
  const offersCount = ref(parseInt(sessionStorage.getItem('offers_count') || '0', 10) || 0)
  const discontinuedCount = ref(parseInt(sessionStorage.getItem('discontinued_count') || '0', 10) || 0)
  const lastLoginAt = ref(parseInt(sessionStorage.getItem('last_login_at') || '0', 10) || 0)
  let keepAliveInterval = null // 👈 Referencia al intervalo

  // ✅ Getter: isAuthenticated
  const isAuthenticated = computed(() => {
    return !!accessToken.value && !!user.value
  })

  const isStaff = computed(() => {
    return isAuthenticated.value && user.value?.is_staff
  })

  // ✅ Acción: login
  const login = async (username, password) => {
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
      localStorage.setItem('session_id', sessionId)

      // ✅ Iniciar el keep-alive solo después de login
      startKeepAlive()

      // Limpiar tracking de vistas por sesión para registrar por cada login
      try {
        sessionStorage.removeItem('view_logged_oferta')
        sessionStorage.removeItem('view_logged_discontinuado')
      } catch (e) {}

      // Después de tener tokens, consultar conteos (ofertas y discontinuados)
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

      // Marca de login para disparar el modal cada vez que se loguea
      lastLoginAt.value = Date.now()
      try { sessionStorage.setItem('last_login_at', String(lastLoginAt.value)) } catch (e) {}

      // Emitir evento global para notificar que el usuario inició sesión
      try { window.dispatchEvent(new Event('user-logged-in')) } catch (e) { /* ignore */ }

      router.push('/productos')
    } catch (error) {
      throw error
    } finally {
      loading.value = false
    }
  }

  // ✅ Acción: logout
  const logout = async () => {
    const sessionId = localStorage.getItem('session_id')

    try {
      await api.post('/api/logout/', { session_id: sessionId })
    } catch (error) {
      console.warn('No se pudo registrar el cierre de sesión:', error)
    } finally {
      // ✅ Limpiar el intervalo al hacer logout
      stopKeepAlive()

      accessToken.value = null
      refreshToken.value = null
      user.value = null

      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('user')
      localStorage.removeItem('session_id')

      window.dispatchEvent(new Event('user-logged-out'))

      router.push('/login')
    }
  }

  // ✅ Iniciar el ping periódico
  const startKeepAlive = () => {
    // Limpiar por si ya existe
    stopKeepAlive()

    keepAliveInterval = setInterval(async () => {
      if (isAuthenticated.value) {
        try {
          await api.post('/api/keep-alive/') // Ajusta la URL según tu API
        } catch (error) {
          console.warn('Error en keep-alive:', error)
          // Opcional: podrías considerar cerrar sesión si falla repetidamente
        }
      }
    }, 10 * 60 * 1000) // Cada 10 minutos (reducido de 5 minutos)
  }

  // ✅ Detener el ping
  const stopKeepAlive = () => {
    if (keepAliveInterval) {
      clearInterval(keepAliveInterval)
      keepAliveInterval = null
    }
  }

  // ✅ Acciones auxiliares
  const setUser = (userData) => {
    user.value = userData
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const setTokens = (access, refresh) => {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  // Función para inicializar desde localStorage
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
        // Opcional: iniciar keep-alive si quieres reanudar la sesión
        // startKeepAlive()
      } catch (error) {
        console.error('Error parsing saved user data:', error)
        // Limpiar datos corruptos
        localStorage.removeItem('user')
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }
  }

  // Inicializar al crear el store
  initializeFromStorage()

  // 👇 Devolver todo
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
    // Opcional: exponer para debug
    // startKeepAlive,
    // stopKeepAlive,
  }
})
