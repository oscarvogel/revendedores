import { ref, onMounted } from 'vue'
import api from '@/services/api'

export function usePermisoDescarga() {
  const puedeDescargarLista = ref(false)
  onMounted(async () => {
    try {
      const { data } = await api.get('/api/permiso-descarga-lista/')
      puedeDescargarLista.value = data.puede_descargar_lista === true
    } catch (error) {
      console.error('No se pudo consultar el permiso de descarga', error)
    }
  })
  return puedeDescargarLista
}
