<template>
  <div class="ui-page space-y-6">
    <PageHeader
      title="Mis comprobantes"
      description="Historial de facturas, pagos y movimientos con filtros para revisar saldos."
    >
      <template #actions>
        <button 
          @click="loadComprobantes(paginacion.current_page)"
          :disabled="loading"
          class="ui-button ui-button-primary px-4 py-2.5 text-sm disabled:opacity-50"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" :class="{ 'animate-spin': loading }">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {{ loading ? 'Actualizando...' : 'Actualizar' }}
        </button>
      </template>
    </PageHeader>

    <!-- Filtros -->
    <div class="ui-panel p-5">
      <h3 class="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
        <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.414A1 1 0 013 6.707V4z" />
        </svg>
        Filtros de Búsqueda
      </h3>
      
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <!-- Fecha Desde -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Fecha Desde</label>
          <input
            v-model="filtros.fecha_desde"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-red-500 focus:border-red-500"
          />
        </div>
        
        <!-- Fecha Hasta -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Fecha Hasta</label>
          <input
            v-model="filtros.fecha_hasta"
            type="date"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-red-500 focus:border-red-500"
          />
        </div>
        
        <!-- Tipo de Comprobante -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">Tipo</label>
          <select
            v-model="filtros.codigo"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-red-500 focus:border-red-500"
          >
            <option value="">Todos</option>
            <option value="F">Facturas</option>
            <option value="D">Débitos</option>
            <option value="R">Pagos/Recibos</option>
            <option value="C">Créditos</option>
          </select>
        </div>
        
        <!-- Botones -->
        <div class="flex items-end gap-2">
          <button
            @click="aplicarFiltros"
            :disabled="loading"
            class="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            Filtrar
          </button>
          <button
            @click="limpiarFiltros"
            class="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 transition-colors"
          >
            Limpiar
          </button>
        </div>
      </div>
    </div>

    <!-- Resumen -->
    <div v-if="!loading && comprobantes.length > 0" class="ui-panel p-5">
      <h3 class="text-lg font-semibold text-gray-900 mb-4">Resumen de Resultados</h3>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div class="bg-blue-50 p-3 rounded-lg">
          <p class="text-blue-600 font-medium">Total Registros</p>
          <p class="text-xl font-bold text-blue-900">{{ paginacion.total_records }}</p>
        </div>
        <div class="bg-green-50 p-3 rounded-lg">
          <p class="text-green-600 font-medium">Total Neto</p>
          <p class="text-lg font-bold text-green-900">${{ formatCurrency(totales.total_neto_filtrado) }}</p>
        </div>
        <div class="bg-purple-50 p-3 rounded-lg">
          <p class="text-purple-600 font-medium">Total Importe</p>
          <p class="text-lg font-bold text-purple-900">${{ formatCurrency(totales.total_importe_filtrado) }}</p>
        </div>
        <div class="bg-red-50 p-3 rounded-lg">
          <p class="text-red-600 font-medium">Saldo Pendiente</p>
          <p class="text-lg font-bold text-red-900">${{ formatCurrency(totales.total_saldo_filtrado) }}</p>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <LoadingState v-if="loading" label="Cargando comprobantes..." />

    <!-- Error State -->
    <div v-else-if="error" class="bg-white rounded-2xl shadow-lg border border-red-300 p-6">
      <div class="flex items-center justify-center text-red-600">
        <svg class="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
        </svg>
        <div class="ml-4">
          <h3 class="text-lg font-medium">Error al cargar comprobantes</h3>
          <p class="text-sm text-gray-600">{{ errorMessage }}</p>
        </div>
      </div>
    </div>

    <!-- Tabla de Comprobantes -->
    <div v-else-if="comprobantes.length > 0" class="ui-panel overflow-hidden">
      <div class="px-6 py-4 border-b border-gray-200">
        <h3 class="text-lg font-semibold text-gray-900">
          Comprobantes (Página {{ paginacion.current_page }} de {{ paginacion.total_pages }})
        </h3>
      </div>
      
      <!-- Tabla Responsive -->
      <div class="overflow-x-auto">
        <table class="ui-table min-w-[1200px]">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Comprobante</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tipo</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Neto</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Total</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Saldo</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Estado</th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vencimiento</th>
              <th class="sticky right-0 z-20 min-w-[15rem] bg-gray-50 px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Acciones</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="comprobante in comprobantes" :key="comprobante.numero" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-medium text-gray-900">{{ comprobante.numero }}</div>
                <div class="text-sm text-gray-500">{{ comprobante.forma_pago }}</div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ formatDate(comprobante.fecha) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span :class="getTipoComprobanteClass(comprobante.codigo)" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
                  {{ comprobante.tipo_comprobante }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-mono">
                ${{ formatCurrency(comprobante.neto) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-mono">
                ${{ formatCurrency(comprobante.total) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-mono">
                <span :class="getSaldoClass(comprobante.saldo)">
                  ${{ formatCurrency(comprobante.saldo) }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span :class="getEstadoClass(comprobante.estado)" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
                  {{ comprobante.estado }}
                </span>
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                <div>{{ formatDate(comprobante.fecha_vencimiento) }}</div>
                <div v-if="comprobante.fecha_primer_vencimiento !== comprobante.fecha_vencimiento" class="text-xs text-gray-500">
                  1° Venc: {{ formatDate(comprobante.fecha_primer_vencimiento) }}
                </div>
              </td>
              <td class="sticky right-0 z-10 min-w-[15rem] bg-white px-4 py-4 text-sm text-gray-500">
                <div class="flex flex-col items-start gap-2 whitespace-normal">
                  <button
                    v-if="['F', 'C', 'D'].includes(comprobante.codigo)"
                    @click="descargarFactura(comprobante)"
                    :disabled="descargando === comprobanteKey(comprobante)"
                    class="inline-flex items-center gap-2 rounded-lg border border-red-700 bg-red-700 px-3 py-2 font-semibold text-white shadow-sm transition-colors hover:border-red-800 hover:bg-red-800 disabled:cursor-wait disabled:opacity-60"
                    :aria-busy="descargando === comprobanteKey(comprobante)"
                    :title="comprobante.codigo === 'F' ? 'Descargar factura PDF' : 'Descargar comprobante PDF'"
                  >
                    <i class="fas fa-download" :class="{ 'animate-pulse': descargando === comprobanteKey(comprobante) }"></i>
                    {{ descargando === comprobanteKey(comprobante) ? 'Descargando…' : (comprobante.codigo === 'F' ? 'Descargar factura' : 'Descargar comprobante') }}
                  </button>
                  <p
                    v-if="errorDescarga && errorDescargaKey === comprobanteKey(comprobante)"
                    class="max-w-[14rem] whitespace-normal text-xs leading-4 text-red-700"
                    role="alert"
                  >{{ errorDescarga }}</p>
                  <button
                    @click="verDetalle(comprobante.numero)"
                    class="inline-flex items-center text-blue-600 transition-colors hover:text-blue-900"
                    title="Ver detalle"
                  >
                    <i class="fas fa-eye mr-1"></i>
                    Ver detalle
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Paginación -->
      <div class="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
        <div class="flex-1 flex justify-between sm:hidden">
          <!-- Paginación móvil -->
          <button
            @click="cambiarPagina(paginacion.current_page - 1)"
            :disabled="!paginacion.has_previous"
            class="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Anterior
          </button>
          <button
            @click="cambiarPagina(paginacion.current_page + 1)"
            :disabled="!paginacion.has_next"
            class="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Siguiente
          </button>
        </div>
        
        <!-- Paginación desktop -->
        <div class="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
          <div>
            <p class="text-sm text-gray-700">
              Mostrando
              <span class="font-medium">{{ ((paginacion.current_page - 1) * 20) + 1 }}</span>
              a
              <span class="font-medium">{{ Math.min(paginacion.current_page * 20, paginacion.total_records) }}</span>
              de
              <span class="font-medium">{{ paginacion.total_records }}</span>
              resultados
            </p>
          </div>
          <div>
            <nav class="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
              <!-- Anterior -->
              <button
                @click="cambiarPagina(paginacion.current_page - 1)"
                :disabled="!paginacion.has_previous"
                class="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="sr-only">Previous</span>
                <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clip-rule="evenodd" />
                </svg>
              </button>
              
              <!-- Páginas -->
              <template v-for="page in getPaginationPages()" :key="page">
                <button
                  v-if="page !== '...'"
                  @click="cambiarPagina(page)"
                  :class="[
                    'relative inline-flex items-center px-4 py-2 border text-sm font-medium',
                    page === paginacion.current_page
                      ? 'z-10 bg-red-50 border-red-500 text-red-600'
                      : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                  ]"
                >
                  {{ page }}
                </button>
                <span v-else class="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                  ...
                </span>
              </template>
              
              <!-- Siguiente -->
              <button
                @click="cambiarPagina(paginacion.current_page + 1)"
                :disabled="!paginacion.has_next"
                class="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="sr-only">Next</span>
                <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd" />
                </svg>
              </button>
            </nav>
          </div>
        </div>
      </div>
    </div>

    <!-- Estado Vacío -->
    <div v-else-if="!loading" class="bg-white rounded-2xl shadow-lg border border-gray-300 p-12">
      <div class="text-center">
        <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <h3 class="mt-2 text-sm font-medium text-gray-900">No hay comprobantes</h3>
        <p class="mt-1 text-sm text-gray-500">No se encontraron comprobantes con los filtros aplicados.</p>
        <div class="mt-6">
          <button
            @click="limpiarFiltros"
            class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700"
          >
            Limpiar filtros
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Modal de Detalle -->
  <DetalleComprobanteModal 
    v-model="mostrarModal" 
    :numero-comprobante="numeroComprobanteSeleccionado"
  />
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { descargarComprobante, getComprobantesCliente } from '@/services/dashboard'
import DetalleComprobanteModal from '@/components/DetalleComprobanteModal.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

// Estados
const comprobantes = ref([])
const loading = ref(false)
const error = ref(false)
const errorMessage = ref('')
const descargando = ref('')
const errorDescarga = ref('')
const errorDescargaKey = ref('')

// Modal de detalle
const mostrarModal = ref(false)
const numeroComprobanteSeleccionado = ref('')

// Filtros
const filtros = ref({
  fecha_desde: '',
  fecha_hasta: '',
  codigo: ''
})

// Paginación
const paginacion = ref({
  current_page: 1,
  total_pages: 1,
  page_size: 20,
  total_records: 0,
  has_next: false,
  has_previous: false
})

// Totales
const totales = ref({
  total_neto_filtrado: 0,
  total_importe_filtrado: 0,
  total_saldo_filtrado: 0
})

// Función para formatear moneda
const formatCurrency = (value) => {
  if (!value) return '0.00'
  return new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

// Función para formatear fecha
// Los comprobantes sin fecha de vencimiento (el ERP los guarda como
// '0000-00-00') llegan como null: se muestran con un guion.
const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr + 'T00:00:00')
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleDateString('es-AR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

// Clases CSS para tipo de comprobante
const getTipoComprobanteClass = (codigo) => {
  const classes = {
    'F': 'bg-blue-100 text-blue-800',
    'D': 'bg-red-100 text-red-800',
    'R': 'bg-green-100 text-green-800',
    'C': 'bg-purple-100 text-purple-800'
  }
  return classes[codigo] || 'bg-gray-100 text-gray-800'
}

// Clases CSS para saldo
const getSaldoClass = (saldo) => {
  if (saldo > 0) return 'text-red-600 font-semibold'
  if (saldo < 0) return 'text-green-600'
  return 'text-gray-900'
}

// Clases CSS para estado
const getEstadoClass = (estado) => {
  return estado === 'Vencido' 
    ? 'bg-red-100 text-red-800' 
    : 'bg-green-100 text-green-800'
}

const comprobanteKey = (comprobante) => `${comprobante.codigo}:${comprobante.numero}`

const descargarFactura = async (comprobante) => {
  const key = comprobanteKey(comprobante)
  descargando.value = key
  errorDescarga.value = ''
  errorDescargaKey.value = key

  try {
    const response = await descargarComprobante(comprobante.codigo, comprobante.numero)
    const url = URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `comprobante-${comprobante.codigo}-${comprobante.numero}.pdf`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (err) {
    const status = err.response?.status
    errorDescarga.value = status === 404
      ? 'No se encontró el comprobante solicitado.'
      : status === 422
        ? 'El comprobante no puede generarse por datos fiscales incompletos o sin autorización.'
        : 'No se pudo descargar el comprobante. Intentá nuevamente más tarde.'
    if (window.Toast) window.Toast.show(errorDescarga.value, 'error', 7000)
  } finally {
    descargando.value = ''
  }
}

// Función para cargar comprobantes
const loadComprobantes = async (page = 1) => {
  loading.value = true
  error.value = false
  
  try {
    const params = {
      page,
      page_size: 20,
      ...filtros.value
    }
    
    // Limpiar parámetros vacíos
    Object.keys(params).forEach(key => {
      if (!params[key]) delete params[key]
    })
    
    const response = await getComprobantesCliente(params)
    
    if (response.success) {
      comprobantes.value = response.data
      paginacion.value = response.pagination
      totales.value = response.totales_generales
      console.log('✅ Comprobantes cargados:', response.data.length)
    } else {
      error.value = true
      errorMessage.value = response.message || 'Error desconocido'
    }
  } catch (err) {
    error.value = true
    errorMessage.value = err.response?.data?.message || err.message || 'Error de conexión'
    console.error('❌ Error al cargar comprobantes:', err)
    
    if (window.Toast) {
      window.Toast.show('Error al cargar comprobantes', 'error', 5000)
    }
  } finally {
    loading.value = false
  }
}

// Aplicar filtros
const aplicarFiltros = () => {
  paginacion.value.current_page = 1
  loadComprobantes(1)
}

// Limpiar filtros
const limpiarFiltros = () => {
  filtros.value = {
    fecha_desde: '',
    fecha_hasta: '',
    codigo: ''
  }
  aplicarFiltros()
}

// Cambiar página
const cambiarPagina = (page) => {
  if (page >= 1 && page <= paginacion.value.total_pages) {
    loadComprobantes(page)
  }
}

// Generar páginas para paginación
const getPaginationPages = () => {
  const current = paginacion.value.current_page
  const total = paginacion.value.total_pages
  const pages = []
  
  if (total <= 7) {
    for (let i = 1; i <= total; i++) {
      pages.push(i)
    }
  } else {
    pages.push(1)
    
    if (current <= 4) {
      for (let i = 2; i <= 5; i++) {
        pages.push(i)
      }
      pages.push('...')
      pages.push(total)
    } else if (current >= total - 3) {
      pages.push('...')
      for (let i = total - 4; i <= total; i++) {
        pages.push(i)
      }
    } else {
      pages.push('...')
      for (let i = current - 1; i <= current + 1; i++) {
        pages.push(i)
      }
      pages.push('...')
      pages.push(total)
    }
  }
  
  return pages
}

// Abrir modal de detalle
const verDetalle = (numeroComprobante) => {
  numeroComprobanteSeleccionado.value = numeroComprobante
  mostrarModal.value = true
}

// Cargar comprobantes al montar el componente
onMounted(() => {
  loadComprobantes()
})
</script>
