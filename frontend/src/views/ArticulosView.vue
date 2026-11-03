<script setup>
import { ref, onMounted, watch, computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'
import { usePermisoDescarga } from '@/services/permisoDescarga'

const puedeDescargarLista = usePermisoDescarga()
import * as XLSX from 'xlsx'

import { cart } from '@/services/cart';
import MobileOrderDrawer from '@/components/MobileOrderDrawer.vue';
import QuickLoadPanel from '@/components/QuickLoadPanel.vue';
import OrderSidebar from '@/components/OrderSidebar.vue';
import ActionButton from '@/components/ui/ActionButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

// Estado del modal de imagen
const showImageModal = ref(false)
const selectedArticulo = ref(null)

// Estado del modal de filtros (móvil)
const showMobileFilters = ref(false)

// Estado del modal de carrito
const modalCarrito = ref({
  visible: false,
  articulo: null,
  tipo: '', // 'C', 'A', 'M' o vacío
  cantidad: 1,
  peso: 0,
  superficie: 0,
  subtotal: 0
})

// --- Filtros ---
const modalidad = ref('retira')
const conImpuestos = ref(true)
const condicionPago = ref('')

// Estado para formas de pago
const formasPago = ref([])
const loadingFormasPago = ref(false)

// Estado de artículos
const articulos = ref([])
const loading = ref(false)
const error = ref(null)
const searchQuery = ref('')
const searchInputRef = ref(null)
const cartSidebarCollapsed = ref(localStorage.getItem('order_sidebar_collapsed') === '1')
const showQuickLoad = ref(false)
const showCommercialConditions = ref(false)

const selectedPaymentLabel = computed(() => {
  const selected = formasPago.value.find(fp => fp.id === condicionPago.value)
  if (!selected) return 'Condición de pago'

  let label = selected.nombre
  if (selected.descuento > 0) label += ` (-${selected.descuento}%)`
  if (selected.punitorio > 0) label += ` (punitorio +${selected.punitorio}%)`
  return label
})

// Autocompletado
const showSuggestions = ref(false)
const suggestions = ref([])

// Paginación
const currentPage = ref(1)
const totalPages = ref(1)
const totalItems = ref(0)
const pageSize = ref(12)
const pageSizeOptions = [12, 24, 36, 48, 60, 72, 84, 96]
const viewMode = ref('grid')

// Detectar si es escritorio
const isDesktop = ref(window.innerWidth >= 768)
const injectedIsSidebarOpen = inject('isSidebarOpen', ref(false))
const injectedIsMobile = inject('isMobile', ref(false))
const hideSearchDueToDrawer = computed(() => injectedIsSidebarOpen.value && injectedIsMobile.value)
const route = useRoute()
const showOnlyDiscontinuados = computed(() => {
  const q = route?.query?.discontinuados
  return q === '1' || q === 'true' || q === 'S'
})

const router = useRouter()
// (Se ha eliminado el modal de ofertas: control de sesión y flags ya no son necesarios)

const showOnlyOferta = computed(() => {
  const q = route?.query?.oferta
  return q === '1' || q === 'true' || q === 'S'
})

// Control de debounce
let searchTimeout = null

const normalizePageSize = (value) => {
  const parsed = Number(value)

  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 12
  }

  const matchingOption = pageSizeOptions.find(option => option === parsed)
  if (matchingOption) {
    return matchingOption
  }

  return 12
}

const pageStartItem = computed(() => {
  if (totalItems.value === 0) return 0
  return (currentPage.value - 1) * pageSize.value + 1
})

const pageEndItem = computed(() => {
  if (totalItems.value === 0) return 0
  return Math.min(currentPage.value * pageSize.value, totalItems.value)
})

const searchTerm = computed(() => searchQuery.value.trim())

const resultsSummary = computed(() => {
  if (!searchTerm.value) {
    return `${totalItems.value} artículos disponibles`
  }

  return `${totalItems.value} resultado${totalItems.value === 1 ? '' : 's'} para "${searchTerm.value}"`
})

const paginationItems = computed(() => {
  if (totalPages.value <= 1) {
    return [{ type: 'page', value: 1 }]
  }

  const siblingCount = isDesktop.value ? 1 : 0
  const firstPage = 1
  const lastPage = totalPages.value
  const leftSibling = Math.max(currentPage.value - siblingCount, firstPage)
  const rightSibling = Math.min(currentPage.value + siblingCount, lastPage)
  const items = []

  items.push({ type: 'page', value: firstPage })

  if (leftSibling > firstPage + 1) {
    items.push({ type: 'ellipsis', value: 'left-ellipsis' })
  }

  const middleStart = Math.max(leftSibling, firstPage + 1)
  const middleEnd = Math.min(rightSibling, lastPage - 1)

  for (let page = middleStart; page <= middleEnd; page += 1) {
    items.push({ type: 'page', value: page })
  }

  if (rightSibling < lastPage - 1) {
    items.push({ type: 'ellipsis', value: 'right-ellipsis' })
  }

  if (lastPage > firstPage) {
    items.push({ type: 'page', value: lastPage })
  }

  return items
})

// Función para formatear moneda
const formatCurrency = (value) => {
  const number = parseFloat(value)
  if (isNaN(number)) return value
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number)
}

// Formatear cantidad/stock para mostrar en la UI
const formatStock = (value) => {
  const n = parseFloat(value)
  if (isNaN(n)) return value || '0'
  // Mostrar sin decimales si es entero, sino hasta 2 decimales
  const opts = Number.isInteger(n) ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 0, maximumFractionDigits: 2 }
  return n.toLocaleString('es-AR', opts)
}

// Función para formatear fecha en formato dd-mm-aaaa
const formatDate = (dateString) => {
  if (!dateString) return ''
  
  try {
    // Intentar varios formatos de fecha que puede enviar el backend
    let date
    
    // Si viene en formato ISO (YYYY-MM-DD o YYYY-MM-DDTHH:MM:SS)
    if (dateString.includes('-')) {
      date = new Date(dateString)
    }
    // Si viene en formato DD/MM/YYYY
    else if (dateString.includes('/')) {
      const parts = dateString.split('/')
      if (parts.length === 3) {
        // Asumir DD/MM/YYYY
        date = new Date(parts[2], parts[1] - 1, parts[0])
      }
    }
    // Si viene como timestamp
    else if (!isNaN(dateString)) {
      date = new Date(parseInt(dateString))
    }
    else {
      // Intentar parsear directamente
      date = new Date(dateString)
    }
    
    // Verificar si la fecha es válida
    if (isNaN(date.getTime())) {
      return dateString // Devolver original si no se puede formatear
    }
    
    // Formatear a dd-mm-aaaa
    const day = date.getDate().toString().padStart(2, '0')
    const month = (date.getMonth() + 1).toString().padStart(2, '0')
    const year = date.getFullYear()
    
    return `${day}-${month}-${year}`
  } catch (error) {
    console.warn('Error formateando fecha:', dateString, error)
    return dateString // Devolver original en caso de error
  }
}

const escapeHtml = (value) => String(value ?? '')
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#039;')

const escapeRegExp = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const highlightMatch = (value) => {
  const safeValue = escapeHtml(value)
  const term = searchTerm.value

  if (!term) return safeValue

  const regex = new RegExp(`(${escapeRegExp(escapeHtml(term))})`, 'ig')
  return safeValue.replace(regex, '<mark class="search-highlight">$1</mark>')
}

// Buscar campo de vencimiento de oferta en el objeto artículo
const ofertaExpiryFields = ['oferta_vencimiento','fecha_venc_oferta','venc_oferta','oferta_vto','oferta_fin','oferta_fecha','fecha_fin_oferta','vencimiento_oferta']
const getOfferExpiry = (art) => {
  if (!art) return null
  for (const f of ofertaExpiryFields) {
    if (art[f]) return art[f]
  }
  return null
}

// === Cargar filtros guardados del localStorage ===
const loadSavedFilters = () => {
  const savedModalidad = localStorage.getItem('articulos_modalidad')
  if (savedModalidad === 'retira' || savedModalidad === 'reparto') {
    modalidad.value = savedModalidad
  }

  const savedImpuestos = localStorage.getItem('articulos_con_impuestos')
  if (savedImpuestos === 'true') {
    conImpuestos.value = true
  } else if (savedImpuestos === 'false') {
    conImpuestos.value = false
  }

  const savedCondicion = localStorage.getItem('condicion_pago')
  if (savedCondicion && formasPago.value.some(fp => fp.id === savedCondicion)) {
    condicionPago.value = savedCondicion
  }

  const savedPageSize = localStorage.getItem('articulos_page_size')
  pageSize.value = normalizePageSize(savedPageSize)

  const savedViewMode = localStorage.getItem('articulos_view_mode')
  viewMode.value = savedViewMode === 'list' ? 'list' : 'grid'
}

// === Guardar filtros en localStorage ===
const saveFilters = () => {
  localStorage.setItem('articulos_modalidad', modalidad.value)
  localStorage.setItem('articulos_con_impuestos', String(conImpuestos.value))
  localStorage.setItem('condicion_pago', condicionPago.value)
}

const setViewMode = (mode) => {
  viewMode.value = mode === 'list' ? 'list' : 'grid'
  localStorage.setItem('articulos_view_mode', viewMode.value)
}

const focusSearchInput = () => {
  if (!searchInputRef.value) return
  searchInputRef.value.focus({ preventScroll: true })
}

const updatePageSize = (value) => {
  const nextPageSize = normalizePageSize(value)

  if (nextPageSize === pageSize.value) {
    return
  }

  pageSize.value = nextPageSize
  localStorage.setItem('articulos_page_size', String(nextPageSize))
  currentPage.value = 1
  fetchArticulos()
}

// === TOAST NOTIFICATIONS (cola) ===
const toasts = ref([])

const showNotification = (message, type = 'info') => {
  const id = Date.now() + Math.random()
  const toast = { id, message, type }

  toasts.value.push(toast)

  // Eliminar automáticamente después de 3 segundos
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, 3000)
}

// Cerrar toast manually
const removeToast = (id) => {
  toasts.value = toasts.value.filter(t => t.id !== id)
}

// === FETCH ARTÍCULOS ===
const fetchArticulos = async () => {
  loading.value = true
  error.value = null
  try {
    // Fetch de favoritos en paralelo
    const favoritesPromise = api.get('/api/favoritos/').then(res => res.data.map(fav => fav.articulo));

    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      modalidad: modalidad.value,
      con_impuestos: conImpuestos.value,
      condicion_pago: condicionPago.value
    };

    if (searchQuery.value.trim()) {
      params.search = searchQuery.value.trim();
    }

    // Si la vista pide solo discontinuados, solicitarlo al backend
    if (showOnlyDiscontinuados.value) {
      params.discontinuados = 1
    }

    if (showOnlyOferta.value) {
      params.oferta = 1
    }

    const responsePromise = api.get('/api/articulos/', { params });

    // Esperar ambas respuestas
    const [articulosResponse, favoriteArticuloIds] = await Promise.all([responsePromise, favoritesPromise]);

    const fetchedArticulos = articulosResponse.data.results;

    // Marcar favoritos y precios disponibles (comportamiento normal)
    articulos.value = fetchedArticulos.map(art => ({
      ...art,
      is_favorito: favoriteArticuloIds.includes(art.clave),
      mostrar_precio: art.mostrar_precio || false,
      consultandoPrecio: false
    }))

    totalItems.value = articulosResponse.data.count;
    totalPages.value = articulosResponse.data.total_pages;
    currentPage.value = articulosResponse.data.current_page;

    updateSuggestions();

    // Ya no mostramos modal de ofertas desde la UI
  } catch (err) {
    showNotification('No se pudieron cargar los artículos. Intente más tarde.', 'error');
    console.error('Error al cargar artículos:', err);
  } finally {
    loading.value = false;
  }
};

// === GESTIONAR FAVORITOS ===
const toggleFavorite = async (articulo) => {
  const originalIsFavorito = articulo.is_favorito;
  articulo.is_favorito = !articulo.is_favorito; // Optimistic update

  try {
    if (articulo.is_favorito) {
      await api.post('/api/favoritos/', { articulo: articulo.clave });
      showNotification('Agregado a favoritos', 'success');
      
      // Si ahora es favorito, actualizar para mostrar el precio
      articulo.mostrar_precio = true;
      // Recargar artículos para obtener precios actualizados
      fetchArticulos();
    } else {
      // El ID para DELETE es la clave del artículo
      const url = `/api/favoritos/${articulo.clave}/`.trim();
      await api.delete(url);
      showNotification('Eliminado de favoritos', 'info');
      
      // Si ya no es favorito, ocultar el precio
      articulo.mostrar_precio = false;
      articulo.precio_lista = null;
    }
  } catch (err) {
    articulo.is_favorito = originalIsFavorito; // Revert on error
    showNotification('No se pudo actualizar el favorito. Intente de nuevo.', 'error');
    console.error('Error al actualizar favorito:', err);
  }
};

// === CONSULTAR PRECIO ===
const consultarPrecio = async (articulo) => {
  try {
    // Mostrar loading en el botón
    const articuloIndex = articulos.value.findIndex(art => art.clave === articulo.clave);
    if (articuloIndex !== -1) {
      articulos.value[articuloIndex].consultandoPrecio = true;
    }

    const consultaData = {
      articulo_clave: articulo.clave,
      modalidad: modalidad.value,
      con_impuestos: conImpuestos.value,
      condicion_pago: condicionPago.value
    };
    
    console.log('Enviando consulta de precio:', consultaData);
    
    const response = await api.post('/api/consultar-precio/', consultaData);
    
    console.log('Respuesta del servidor:', response.data);
    
    if (response.data.success && response.data.articulo.precio_lista !== null) {
      // Actualizar el artículo con el precio obtenido
      if (articuloIndex !== -1) {
        articulos.value[articuloIndex].precio_lista = response.data.articulo.precio_lista;
        articulos.value[articuloIndex].mostrar_precio = true;
        articulos.value[articuloIndex].consultandoPrecio = false;
      }
      
      showNotification(`Precio: $${formatCurrency(response.data.articulo.precio_lista)}`, 'success');
    } else {
      throw new Error(`Precio no disponible: ${response.data.articulo.precio_lista}`);
    }
  } catch (err) {
    console.error('Error al consultar precio:', err);
    
    // Quitar loading del botón
    const articuloIndex = articulos.value.findIndex(art => art.clave === articulo.clave);
    if (articuloIndex !== -1) {
      articulos.value[articuloIndex].consultandoPrecio = false;
    }
    
    const errorMsg = err.response?.data?.error || err.message || 'No se pudo consultar el precio. Intente de nuevo.';
    showNotification(errorMsg, 'error');
  }
};

// === FETCH FORMAS DE PAGO ===
const fetchFormasPago = async () => {
  loadingFormasPago.value = true
  try {
    const response = await api.get('/api/formas-pago/')
    formasPago.value = response.data
    loadSavedFilters()
  } catch (err) {
    console.error('Error al cargar formas de pago:', err)
    condicionPago.value = ''
    showNotification('No se pudieron cargar las condiciones de pago.', 'error')
  } finally {
    loadingFormasPago.value = false
  }
}

// === DEBOUNCE EN BÚSQUEDA ===
watch(searchQuery, () => {
  if (searchTimeout) clearTimeout(searchTimeout)

  if (!searchQuery.value.trim()) {
    currentPage.value = 1
    fetchArticulos()
    return
  }

  searchTimeout = setTimeout(() => {
    currentPage.value = 1
    fetchArticulos()
  }, 500)
})

// Al cambiar condición de pago
watch(condicionPago, () => {
  saveFilters()
  fetchArticulos()
})

// Al cambiar otros filtros
watch([modalidad, conImpuestos], () => {
  saveFilters()
  currentPage.value = 1
  fetchArticulos()
})

// Si cambia la query `discontinuados`, recargar artículos
watch(() => route.query.discontinuados, () => {
  currentPage.value = 1
  fetchArticulos()
})

// Reaccionar cuando cambia la query `oferta`
watch(() => route.query.oferta, () => {
  currentPage.value = 1
  fetchArticulos()
})

// Registrar vistas de ofertas/discontinuados (una vez por session)
const trackArticuloView = async (tipo) => {
  const key = `view_logged_${tipo}`
  try {
    if (sessionStorage.getItem(key)) return
    await api.post('/api/track-articulos-view/', { tipo })
    sessionStorage.setItem(key, '1')
  } catch (e) {
    // no bloquear UI si falla el tracking
  }
}

watch(() => route.query.discontinuados, (val) => {
  if (val) trackArticuloView('discontinuado')
})

watch(() => route.query.oferta, (val) => {
  if (val) trackArticuloView('oferta')
})

// Actualizar sugerencias
const updateSuggestions = () => {
  const query = searchQuery.value.toLowerCase()
  if (!query) {
    suggestions.value = []
    return
  }

  suggestions.value = articulos.value
    .filter(art =>
      art.clave.toLowerCase().includes(query) ||
      art.nombre.toLowerCase().includes(query)
    )
    .slice(0, 5)
}

// Cambiar página
const changePage = (page) => {
  if (page >= 1 && page <= totalPages.value && page !== currentPage.value) {
    currentPage.value = page
    fetchArticulos()
  }
}

// Limpiar búsqueda
const clearSearch = () => {
  searchQuery.value = ''
  currentPage.value = 1
  fetchArticulos()
}

// Seleccionar sugerencia
const selectSuggestion = (articulo) => {
  searchQuery.value = articulo.nombre
  showSuggestions.value = false
  currentPage.value = 1
  fetchArticulos()
}

// Exportar a Excel (Favoritos únicamente)
const exportToExcel = async () => {
  try {
    // Mostrar loading notification
    showNotification('Preparando exportación de favoritos...', 'info')
    
    // Llamar al endpoint optimizado de backend
    const response = await api.get('/api/exportar-favoritos/', {
      params: {
        modalidad: modalidad.value,
        con_impuestos: conImpuestos.value,
        condicion_pago: condicionPago.value
      }
    })
    
    if (response.data.success) {
      const { data, total_articulos, parametros, message } = response.data
      
      if (data.length === 0) {
        showNotification('No tienes artículos favoritos para exportar.', 'info')
        return
      }
      
      // Crear archivo Excel con los datos optimizados del backend
      const excelData = data.map(art => ({
        'Clave': art.clave,
        'Nombre': art.nombre,
        'Unidad': art.unidad,
        'Peso': art.peso,
        'IVA': `${art.iva}%`,
        'Precio Actual': art.precio_actual,
        'Modalidad': art.modalidad,
        'Con Impuestos': art.con_impuestos ? 'Sí' : 'No',
        'Última Actualización': art.ultima_actualizacion,
      }))

      const worksheet = XLSX.utils.json_to_sheet(excelData)
      const workbook = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Artículos Favoritos')
      
      // Generar nombre de archivo con parámetros
      const fecha = new Date().toISOString().split('T')[0]
      const fileName = `favoritos_${parametros.modalidad}_${parametros.con_impuestos ? 'con' : 'sin'}_impuestos_${fecha}.xlsx`
      
      XLSX.writeFile(workbook, fileName)
      
      showNotification(`✅ ${total_articulos} artículos favoritos exportados correctamente.`, 'success')
      
    } else {
      showNotification('Error al preparar la exportación.', 'error')
    }
    
  } catch (error) {
    console.error('Error en exportación:', error)
    if (error.response?.data?.error) {
      showNotification(error.response.data.error, 'error')
    } else {
      showNotification('Error al exportar favoritos. Intenta nuevamente.', 'error')
    }
  }
}

// Función para abrir imagen
const openImageModal = (articulo) => {
  if (!articulo || !articulo.imagen) {
    showNotification('Este artículo no tiene imagen disponible.', 'error')
    return
  }
  selectedArticulo.value = articulo
  showImageModal.value = true
}

// Cerrar modal de imagen
const closeImageModal = () => {
  showImageModal.value = false
  selectedArticulo.value = null
}

// Cerrar modal de filtros
const closeFilterModal = () => {
  showMobileFilters.value = false
}

// Aplicar filtros (cierra modal y recarga)
const applyFilters = () => {
  saveFilters()
  currentPage.value = 1
  fetchArticulos()
  closeFilterModal()
}

// === FUNCIONES DEL MODAL DE CARRITO ===
const abrirModalCarrito = (articulo) => {
  console.log('📦 Abriendo modal para artículo:', articulo)
  
  // Si es campoa1='c', inicializar con 1 artículo y su peso correspondiente
  const cantidadInicial = 1
  const campoa1Inicial = (articulo.campoa1 || '').toLowerCase()
  const pesoInicial = campoa1Inicial === 'c' ? (parseFloat(articulo.peso) || 0) : 0
  
  modalCarrito.value = {
    visible: true,
    articulo: articulo,
    tipo: articulo.campoa1 || '',
    cantidad: cantidadInicial,
    peso: pesoInicial,
    superficie: 0,
    subtotal: articulo.precio_lista || 0
  }
  
  console.log('🔍 Tipo de artículo (campoa1):', articulo.campoa1)
  console.log('🔍 Tipo de stock (campoa1):', articulo.campoa1)
  console.log('📏 Peso unitario por artículo:', articulo.peso, 'kg')
  console.log('📏 Mts2:', articulo.mts2)
}

const cerrarModalCarrito = () => {
  modalCarrito.value = {
    visible: false,
    articulo: null,
    tipo: '',
    cantidad: 1,
    peso: 0,
    superficie: 0,
    subtotal: 0
  }
}

const calcularCantidadPorSuperficie = () => {
  if (modalCarrito.value.tipo === 'A' && modalCarrito.value.articulo?.mts2 > 0 && modalCarrito.value.superficie > 0) {
    // Calcular cantidad de cajas necesarias (siempre redondear hacia arriba)
    const cajas = Math.ceil(modalCarrito.value.superficie / modalCarrito.value.articulo.mts2)
    modalCarrito.value.cantidad = cajas
    
    // Calcular subtotal
    modalCarrito.value.subtotal = cajas * (modalCarrito.value.articulo.precio_lista || 0)
    
    console.log(`📦 Superficie: ${modalCarrito.value.superficie} m²`)
    console.log(`📦 M² por caja: ${modalCarrito.value.articulo.mts2}`)
    console.log(`📦 Cajas calculadas: ${cajas}`)
  }
}

const agregarAlCarrito = () => {
  if (!modalCarrito.value.articulo || modalCarrito.value.cantidad <= 0) {
    showNotification('Debe ingresar una cantidad válida', 'error')
    return
  }
  
  let cantidadAAgregar = modalCarrito.value.cantidad
  let superficieReal = modalCarrito.value.superficie
  
  // Validación especial para tipo A con mts2: asegurar que la superficie sea múltiplo
  if (modalCarrito.value.tipo === 'A' && modalCarrito.value.articulo.mts2 > 0 && modalCarrito.value.superficie > 0) {
    // Recalcular la cantidad de cajas necesarias para cubrir la superficie
    const cajasNecesarias = Math.ceil(modalCarrito.value.superficie / modalCarrito.value.articulo.mts2)
    
    // Calcular la superficie real que se cubrirá (múltiplo exacto)
    superficieReal = cajasNecesarias * modalCarrito.value.articulo.mts2
    
    // La cantidad a agregar es la superficie total en m² (no las cajas)
    cantidadAAgregar = superficieReal
    
    console.log(`🔧 Superficie solicitada: ${modalCarrito.value.superficie} m²`)
    console.log(`� Cajas necesarias: ${cajasNecesarias}`)
    console.log(`📏 Superficie real (múltiplo): ${superficieReal} m²`)
    console.log(`� Cantidad a agregar al carrito: ${cantidadAAgregar} m²`)
  }
  
  console.log('🛒 Agregando al carrito:', {
    clave: modalCarrito.value.articulo.clave,
    nombre: modalCarrito.value.articulo.nombre,
    cantidad: cantidadAAgregar,
    peso: modalCarrito.value.peso,
    superficie: superficieReal
  })
  
  // Agregar al carrito pasando la cantidad como segundo parámetro
  cart.add(modalCarrito.value.articulo, cantidadAAgregar)
  
  // Mostrar notificación personalizada
  let mensaje = `${modalCarrito.value.cantidad} unidad(es) agregada(s) al carrito`
  
  const campoa1Lower = (modalCarrito.value.articulo.campoa1 || '').toLowerCase()
  
  if (modalCarrito.value.tipo === 'A' && modalCarrito.value.superficie > 0) {
    const cajas = Math.ceil(modalCarrito.value.superficie / modalCarrito.value.articulo.mts2)
    mensaje = `${superficieReal.toFixed(2)} m² agregados al carrito (${cajas} caja${cajas > 1 ? 's' : ''})`
  } else if (campoa1Lower === 'c' && modalCarrito.value.peso > 0) {
    // Para campoa1='c': mostrar cantidad de artículos y peso total
    mensaje = `${modalCarrito.value.cantidad} artículo(s) agregado(s) (${modalCarrito.value.peso} kg total)`
  } else if ((modalCarrito.value.tipo === 'C' || modalCarrito.value.tipo === 'M') && modalCarrito.value.peso > 0) {
    mensaje += ` (${modalCarrito.value.peso} kg)`
  }
  
  showNotification(mensaje, 'success')
  
  // Cerrar modal
  cerrarModalCarrito()
}

// Watch para calcular subtotal y peso cuando cambia la cantidad
watch(() => modalCarrito.value.cantidad, (newCantidad, oldCantidad) => {
  if (!modalCarrito.value.articulo || newCantidad <= 0) return

  const campoa1Lower = (modalCarrito.value.articulo.campoa1 || '').toLowerCase()

  // Si es campoa1='c', calcular el peso automáticamente (peso total = cantidad × peso_unitario)
  if (campoa1Lower === 'c') {
    const pesoUnitario = parseFloat(modalCarrito.value.articulo.peso) || 0
    modalCarrito.value.peso = newCantidad * pesoUnitario
    console.log(`⚖️ Calculando peso total: ${newCantidad} artículos × ${pesoUnitario} kg = ${modalCarrito.value.peso} kg`)
  }
  
  // SIEMPRE calcular subtotal por cantidad de artículos (no por peso)
  modalCarrito.value.subtotal = newCantidad * (modalCarrito.value.articulo.precio_lista || 0)
})

// Watch para calcular cantidad cuando cambia el peso (solo para campoa1='c')
watch(() => modalCarrito.value.peso, (newPeso, oldPeso) => {
  console.log('🔔 Watch de peso disparado:', { newPeso, oldPeso, articulo: modalCarrito.value.articulo?.clave, campoa1: modalCarrito.value.articulo?.campoa1 })
  
  if (!modalCarrito.value.articulo) {
    console.log('❌ No hay artículo en el modal')
    return
  }

  // Si es campoa1='c' (mayúscula o minúscula) y se cambió el peso manualmente
  const campoa1Lower = (modalCarrito.value.articulo.campoa1 || '').toLowerCase()
  
  if (campoa1Lower === 'c' && newPeso > 0) {
    const pesoUnitario = parseFloat(modalCarrito.value.articulo.peso) || 1
    const cantidadCalculada = newPeso / pesoUnitario
    
    console.log(`🔢 Datos del cálculo:`)
    console.log(`   Peso ingresado: ${newPeso} kg`)
    console.log(`   Peso unitario: ${pesoUnitario} kg/artículo`)
    console.log(`   Cantidad calculada: ${cantidadCalculada} artículos`)
    
    // Redondear para evitar decimales extraños
    const cantidadRedondeada = Math.round(cantidadCalculada * 100) / 100
    
    // Solo actualizar si es diferente (para evitar loops infinitos)
    if (Math.abs(modalCarrito.value.cantidad - cantidadRedondeada) > 0.01) {
      console.log(`✅ Actualizando cantidad de ${modalCarrito.value.cantidad} a ${cantidadRedondeada}`)
      modalCarrito.value.cantidad = cantidadRedondeada
      
      // El subtotal se calculará automáticamente por el watch de cantidad
    } else {
      console.log(`⏭️ No se actualiza, cantidad ya es ${cantidadRedondeada}`)
    }
  } else {
    console.log(`⏭️ No aplica cálculo. campoa1='${campoa1Lower}', peso=${newPeso}`)
  }
  
  // Para tipos C y M que NO son campoa1='c', calcular subtotal por peso
  if (campoa1Lower !== 'c' && (modalCarrito.value.tipo === 'C' || modalCarrito.value.tipo === 'M') && newPeso > 0) {
    modalCarrito.value.subtotal = newPeso * (modalCarrito.value.articulo.precio_lista || 0)
  }
})

// === CARGA RÁPIDA DESDE TARJETAS ===
const quickQuantities = ref({})

const getCartItem = (articulo) => cart.items.find(item => item.articulo.clave === articulo.clave)
const isInCart = (articulo) => Boolean(getCartItem(articulo))

const getQuickStep = (articulo) => {
  const campoa1 = (articulo.campoa1 || '').toLowerCase()
  const mts2 = parseFloat(articulo.mts2) || 0
  return campoa1 === 'a' && mts2 > 0 ? mts2 : 1
}

const getQuickQuantity = (articulo) => {
  const stored = quickQuantities.value[articulo.clave]
  if (stored !== undefined && stored !== null && stored !== '') return Number(stored)
  const existing = getCartItem(articulo)
  if (existing) return Number(existing.cantidad)
  return getQuickStep(articulo)
}

const setQuickQuantity = (articulo, value) => {
  const step = getQuickStep(articulo)
  const parsed = Number(value)
  let next = Number.isFinite(parsed) && parsed > 0 ? parsed : step
  if ((articulo.campoa1 || '').toLowerCase() === 'a' && step > 0) {
    next = Math.max(step, Math.ceil(next / step) * step)
  } else {
    next = Math.max(1, next)
  }
  quickQuantities.value = { ...quickQuantities.value, [articulo.clave]: Number(next.toFixed(3)) }
}

const incrementQuickQuantity = (articulo) => setQuickQuantity(articulo, getQuickQuantity(articulo) + getQuickStep(articulo))
const decrementQuickQuantity = (articulo) => setQuickQuantity(articulo, Math.max(getQuickStep(articulo), getQuickQuantity(articulo) - getQuickStep(articulo)))

const quickQuantityHelper = (articulo) => {
  const campoa1 = (articulo.campoa1 || '').toLowerCase()
  const mts2 = parseFloat(articulo.mts2) || 0
  if (campoa1 === 'a' && mts2 > 0) {
    const cajas = Math.round(getQuickQuantity(articulo) / mts2)
    return `${cajas} caja${cajas === 1 ? '' : 's'} · ${mts2} m²/caja`
  }
  return isInCart(articulo) ? `En pedido: ${getCartItem(articulo).cantidad}` : ''
}

const quickAddToCart = (articulo) => {
  const cantidad = getQuickQuantity(articulo)
  const existing = getCartItem(articulo)
  if (existing) {
    cart.updateQuantity(articulo.clave, cantidad)
  } else {
    cart.add(articulo, cantidad)
  }
  quickQuantities.value = { ...quickQuantities.value, [articulo.clave]: cantidad }
  showNotification(`${articulo.nombre}: ${cantidad} agregado${existing ? ' / actualizado' : ''} en el pedido`, 'success')
}

// Detectar redimensionamiento
onMounted(() => {
  window.addEventListener('resize', () => {
    isDesktop.value = window.innerWidth >= 768
  })

  fetchFormasPago()
  fetchArticulos()

  if (route.query.discontinuados) {
    trackArticuloView('discontinuado')
  }
  if (route.query.oferta) {
    trackArticuloView('oferta')
  }

  window.setTimeout(focusSearchInput, 150)
})
</script>

<template>
  <div class="ui-page pb-20 xl:pb-0">
    <main class="main-content">
      <div
        class="grid items-start gap-4 transition-[grid-template-columns] duration-200"
        :class="cartSidebarCollapsed
          ? 'xl:grid-cols-[minmax(0,1fr)_68px]'
          : 'xl:grid-cols-[minmax(0,1fr)_380px]'"
      >
        <div class="min-w-0 space-y-4">



        <!-- Barra de búsqueda -->
        <div v-show="!hideSearchDueToDrawer" class="mobile-search-card relative !z-[5] rounded-lg border border-red-200 bg-white shadow-md" style="z-index:5">
          <div class="flex flex-col gap-3 border-b border-gray-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div>
              <p class="text-sm font-black text-gray-950">Armar pedido</p>
              <p class="text-xs font-medium text-gray-500">Buscá por clave, nombre o código y agregá productos sin salir del catálogo.</p>
            </div>
            <div class="flex flex-wrap gap-2 text-xs font-bold">
              <RouterLink to="/productos?oferta=1" class="rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-green-800 hover:bg-green-100">Ofertas</RouterLink>
              <RouterLink to="/productos?discontinuados=1" class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800 hover:bg-amber-100">Discontinuados</RouterLink>
              <button type="button" class="rounded-lg border border-gray-200 bg-white px-3 py-2 text-gray-700 hover:bg-gray-50" @click="clearSearch">Ver todos</button>
              <button type="button" class="rounded-lg border border-gray-900 bg-gray-900 px-3 py-2 text-white hover:bg-black" @click="showQuickLoad = true">Carga rápida</button>
              <button v-if="puedeDescargarLista" type="button" class="inline-flex items-center gap-2 rounded-lg border border-green-600 bg-green-600 px-3 py-2 text-white hover:bg-green-700" @click="exportToExcel">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                Descargar lista
              </button>
            </div>
          </div>
          <div class="mobile-search-body px-4 py-3 sm:px-5">
          <div class="mx-auto flex max-w-6xl flex-col gap-3 lg:flex-row">
            <div class="mobile-search-input relative flex-grow rounded-lg border-2 border-red-300 bg-white shadow-sm transition focus-within:border-red-600 focus-within:shadow-lg">
              <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 sm:pl-4">
                <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-red-600 text-white shadow-sm sm:h-9 sm:w-9">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
              </div>
              <input
                ref="searchInputRef"
                v-model="searchQuery"
                placeholder="Clave, nombre o código..."
                class="h-12 w-full rounded-lg border-0 bg-transparent py-3 pl-14 pr-4 text-base font-bold text-gray-950 placeholder:text-gray-400 focus:outline-none sm:h-14 sm:pl-16 sm:pr-24 sm:text-lg"
              />
              <div class="pointer-events-none absolute inset-y-0 right-0 hidden items-center pr-4 sm:flex">
                <div v-if="loading && searchQuery" class="animate-spin h-5 w-5 text-gray-400">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                </div>
                <span v-else-if="searchTerm" class="rounded-full bg-red-50 px-3 py-1 text-xs font-bold text-red-700">
                  buscando
                </span>
              </div>
            </div>

            <button
              @click="clearSearch"
              class="mobile-clear-button inline-flex h-12 w-full items-center justify-center rounded-lg border border-gray-200 bg-white px-5 text-sm font-bold text-red-700 shadow-sm hover:bg-red-50 sm:h-14 lg:w-auto"
            >
              Limpiar
            </button>
          </div>
          </div>

          <!-- Autocompletado -->
          <ul
            v-if="showSuggestions && suggestions.length > 0"
            class="absolute z-20 mt-2 w-full max-h-72 overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg"
          >
            <li
              v-for="sug in suggestions"
              :key="sug.clave"
              @click="selectSuggestion(sug)"
              class="cursor-pointer border-b px-4 py-3 text-sm last:border-b-0 hover:bg-red-50"
            >
              <strong>{{ sug.clave }}</strong> - {{ sug.nombre }}
            </li>
          </ul>
        </div>

        <!-- Botón Filtros (solo móvil) -->
        <button
          v-if="!isDesktop"
          @click="showMobileFilters = true"
            class="inline-flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-bold text-gray-800 shadow-sm"
        >
          <span class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.207A1 1 0 013 6.5V4z" />
            </svg>
            Filtros
          </span>
          <span
            v-if="modalidad !== 'retira' || !conImpuestos || condicionPago"
            class="w-2 h-2 bg-red-500 rounded-full"
          ></span>
        </button>

        <!-- Condiciones comerciales compactas (desktop) -->
        <div v-if="isDesktop" class="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
          <div v-if="!showCommercialConditions" class="flex flex-wrap items-center gap-2">
            <span class="text-[11px] font-black uppercase tracking-wide text-gray-500">Condiciones</span>
            <span class="max-w-[520px] truncate rounded-full bg-gray-100 px-3 py-1.5 text-xs font-bold text-gray-800">{{ selectedPaymentLabel }}</span>
            <span class="rounded-full bg-red-50 px-3 py-1.5 text-xs font-bold text-red-800">{{ modalidad === 'retira' ? 'Retira' : 'Reparto' }}</span>
            <span class="rounded-full bg-red-50 px-3 py-1.5 text-xs font-bold text-red-800">{{ conImpuestos ? 'Con impuestos' : 'Sin impuestos' }}</span>
            <button type="button" class="ml-auto rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-black text-gray-800 transition hover:border-red-300 hover:bg-red-50 hover:text-red-700" @click="showCommercialConditions = true">Cambiar</button>
          </div>

          <template v-else>
            <div class="mb-2 flex items-center justify-between gap-3">
              <div>
                <p class="text-xs font-black uppercase tracking-wide text-gray-500">Condiciones comerciales</p>
                <p class="text-[11px] font-medium text-gray-400">Se guardan automáticamente</p>
              </div>
              <button type="button" class="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-black text-gray-800 transition hover:border-red-300 hover:bg-red-50 hover:text-red-700" @click="showCommercialConditions = false">Listo</button>
            </div>
            <div class="grid grid-cols-1 gap-3 md:grid-cols-[minmax(280px,1.4fr)_minmax(220px,0.8fr)_minmax(260px,0.9fr)]">
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-2.5">
                <label class="mb-1 block text-[11px] font-bold uppercase text-gray-500">Condición de Pago</label>
                <select v-model="condicionPago" class="ui-field border-gray-300 px-3 py-2 text-sm font-semibold shadow-sm" :disabled="loadingFormasPago">
                  <option v-for="fp in formasPago" :key="fp.id" :value="fp.id">
                    {{ fp.nombre }}
                    <template v-if="fp.descuento > 0"> (-{{ fp.descuento }}%)</template>
                    <template v-if="fp.punitorio > 0"> (punitorio +{{ fp.punitorio }}%)</template>
                  </option>
                </select>
                <p v-if="loadingFormasPago" class="mt-1 text-xs text-gray-500">Cargando...</p>
              </div>
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-2.5">
                <label class="mb-1 block text-[11px] font-bold uppercase text-gray-500">Modalidad</label>
                <div class="grid grid-cols-2 gap-2 rounded-lg bg-white p-1 shadow-inner">
                  <button type="button" class="rounded-md px-3 py-2 text-sm font-bold transition" :class="modalidad === 'retira' ? 'bg-red-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'" @click="modalidad = 'retira'">Retira</button>
                  <button type="button" class="rounded-md px-3 py-2 text-sm font-bold transition" :class="modalidad === 'reparto' ? 'bg-red-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'" @click="modalidad = 'reparto'">Reparto</button>
                </div>
              </div>
              <div class="rounded-lg border border-gray-200 bg-gray-50 p-2.5">
                <label class="mb-1 block text-[11px] font-bold uppercase text-gray-500">Precio</label>
                <div class="grid grid-cols-2 gap-2 rounded-lg bg-white p-1 shadow-inner">
                  <button type="button" class="rounded-md px-3 py-2 text-sm font-bold transition" :class="conImpuestos ? 'bg-red-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'" @click="conImpuestos = true">Con impuestos</button>
                  <button type="button" class="rounded-md px-3 py-2 text-sm font-bold transition" :class="!conImpuestos ? 'bg-red-600 text-white shadow-sm' : 'text-gray-600 hover:bg-gray-100'" @click="conImpuestos = false">Sin impuestos</button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <!-- Mensaje de error -->
        <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-800">
          {{ error }}
        </div>

        <div class="products-view-toolbar ui-panel flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p class="text-sm font-bold text-gray-950">Visualización de productos</p>
            <p class="text-sm text-gray-500">
              Mostrando {{ pageStartItem }}-{{ pageEndItem }} de {{ totalItems }} artículos
            </p>
            <p
              class="mt-1 inline-flex rounded-full px-3 py-1 text-xs font-bold"
              :class="searchTerm ? 'bg-red-50 text-red-800' : 'bg-gray-100 text-gray-600'"
            >
              {{ resultsSummary }}
            </p>
          </div>

          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 text-sm text-gray-700">
              <span>Productos por página</span>
              <select
                :value="pageSize"
                class="ui-field px-3 py-2"
                @change="updatePageSize($event.target.value)"
              >
                <option v-for="size in pageSizeOptions" :key="size" :value="size">
                  {{ size }}
                </option>
              </select>
            </label>

            <button
              v-if="puedeDescargarLista"
              type="button"
              class="inline-flex items-center gap-2 rounded-lg border border-green-600 bg-green-600 px-4 py-2 text-sm font-bold text-white shadow-sm hover:bg-green-700"
              @click="exportToExcel"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Descargar lista
            </button>
            <div class="inline-flex rounded-lg border border-gray-300 bg-gray-50 p-1">
              <button
                type="button"
                class="rounded-md px-3 py-2 text-sm font-medium transition"
                :class="viewMode === 'grid' ? 'bg-white text-red-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
                @click="setViewMode('grid')"
              >
                Grilla
              </button>
              <button
                type="button"
                class="rounded-md px-3 py-2 text-sm font-medium transition"
                :class="viewMode === 'list' ? 'bg-white text-red-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'"
                @click="setViewMode('list')"
              >
                Detalle
              </button>
            </div>
          </div>
        </div>

        <!-- Cargando -->
        <LoadingState v-if="loading && articulos.length === 0" label="Cargando artículos..." />

        <!-- Vista grilla -->
        <div
          v-else-if="articulos.length > 0 && viewMode === 'grid'"
          class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3"
        >
          <div
            v-for="art in articulos"
            :key="art.clave"
            :class="[
              'relative flex flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition hover:border-red-200 hover:shadow-md',
              art.discontinuado === 'S' ? 'bg-yellow-50 border border-yellow-300 opacity-95' : '',
              art.oferta === 'S' ? 'bg-green-50 border border-green-300 offer-animate' : '',
              (art.discontinuado !== 'S' && art.oferta !== 'S') ? 'bg-white' : ''
            ]"
          >
            <div v-if="art.discontinuado === 'S'" class="absolute top-3 right-3 bg-yellow-500 text-white text-xs font-semibold px-2 py-1 rounded">Discontinuado</div>
            <div v-if="art.oferta === 'S'" class="absolute top-3 left-3 bg-green-600 text-white text-xs font-semibold px-2 py-1 rounded">Oferta</div>
            <!-- Imagen del artículo -->
            <div class="relative h-40 bg-gray-100 border-b">
              <img
                v-if="art.imagen"
                :src="art.imagen"
                :alt="art.nombre"
                class="w-full h-full object-contain p-3 cursor-pointer"
                @click="openImageModal(art)"
              />
              <div
                v-else
                class="w-full h-full flex items-center justify-center text-gray-400 text-sm"
                @click="showNotification('No hay imagen disponible', 'info')"
              >
                Sin imagen
              </div>
            </div>

            <!-- Contenido de la tarjeta -->
              <div class="flex flex-1 flex-col p-4">
              <div class="flex justify-between items-start">
                <h3
                  class="text-lg font-bold text-gray-900 line-clamp-2 flex-1"
                  :title="art.nombre"
                  v-html="highlightMatch(art.nombre)"
                ></h3>
                  <!-- Mostrar fecha de vencimiento de oferta si existe -->
                  <div v-if="art.oferta === 'S'" class="ml-3">
                    <p v-if="getOfferExpiry(art)" class="text-sm text-green-800 font-semibold offer-expiry ml-3">Vence: {{ formatDate(getOfferExpiry(art)) }}</p>
                  </div>
                <button
                  @click.stop="toggleFavorite(art)"
                  class="p-1 rounded-full text-gray-400 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-colors duration-200"
                  :class="{ 'text-red-500': art.is_favorito }"
                  aria-label="Añadir o quitar de favoritos"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" :class="{ 'fill-current': art.is_favorito }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                  </svg>
                </button>
              </div>
              <p class="text-sm text-gray-500 mt-1">
                Clave:
                <span class="font-semibold text-gray-800" v-html="highlightMatch(art.clave)"></span>
              </p>

              <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div>
                  <p class="text-gray-500">Unidad</p>
                  <p class="font-semibold">{{ art.unidad }}</p>
                </div>
                <div>
                  <p class="text-gray-500">Peso</p>
                  <p class="font-semibold">{{ art.peso }}</p>
                </div>
                <!-- Mostrar mts2 por caja si es mayor que 0 -->
                <div v-if="art.mts2 && parseFloat(art.mts2) > 0">
                  <p class="text-gray-500">Mts² por caja</p>
                  <p class="font-semibold text-blue-600">{{ formatCurrency(art.mts2) }} m²</p>
                </div>
                <div v-else>
                  <p class="text-gray-500">IVA</p>
                  <p class="font-semibold">{{ art.iva }}%</p>
                </div>
                <div v-if="!(art.mts2 && parseFloat(art.mts2) > 0)">
                  <p class="text-gray-500">Últ. Act.</p>
                  <p class="font-semibold">{{ formatDate(art.ultact) }}</p>
                </div>
                <!-- Mostrar IVA en la segunda fila si hay mts2 -->
                <div v-if="art.mts2 && parseFloat(art.mts2) > 0">
                  <p class="text-gray-500">IVA</p>
                  <p class="font-semibold">{{ art.iva }}%</p>
                </div>
              </div>

              <!-- Mostrar stock prominente para artículos en oferta: barra a todo ancho -->
              <div v-if="art.oferta === 'S'" class="w-full mt-4">
                <div class="w-full bg-green-700 text-white text-sm font-bold px-3 py-2 rounded-lg text-center">Stock disponible: {{ formatStock(art.stock) }}</div>
              </div>

              <div class="mt-4 flex flex-wrap items-end gap-2 border-t border-gray-200 pt-3">
                <!-- Mostrar precio si está disponible -->
                <div v-if="art.mostrar_precio && art.precio_lista">
                    <p class="text-xs font-bold uppercase text-gray-500">Precio</p>
                    <p class="line-clamp-1 text-left text-xl font-black text-red-700">$ {{ formatCurrency(art.precio_lista) }}</p>
                </div>
                <!-- Mostrar botón "Ver Precio" si no se muestra el precio -->
                <div v-else class="flex-1">
                    <button 
                      @click="consultarPrecio(art)"
                      :disabled="art.consultandoPrecio"
                      :class="art.consultandoPrecio ? 'bg-gray-400 cursor-not-allowed' : 'border border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100'"
                      class="ui-button px-4 py-2 text-sm transition"
                    >
                      <div v-if="art.consultandoPrecio" class="animate-spin h-4 w-4 border-2 border-blue-700 border-t-transparent rounded-full"></div>
                      <span v-if="art.consultandoPrecio">Consultando...</span>
                      <span v-else>Ver precio</span>
                    </button>
                </div>
                
                <div v-if="art.mostrar_precio && art.precio_lista" class="ml-auto min-w-[150px]">
                  <div class="grid grid-cols-[36px_minmax(56px,1fr)_36px] overflow-hidden rounded-lg border border-gray-300 bg-white">
                    <button type="button" class="h-10 font-black text-gray-700 hover:bg-gray-100" @click="decrementQuickQuantity(art)" :aria-label="`Restar ${art.nombre}`">−</button>
                    <input type="number" :min="getQuickStep(art)" :step="getQuickStep(art)" :value="getQuickQuantity(art)" class="h-10 w-full border-x border-gray-200 text-center text-sm font-black text-gray-950 focus:outline-none" @change="setQuickQuantity(art, $event.target.value)" />
                    <button type="button" class="h-10 font-black text-gray-700 hover:bg-gray-100" @click="incrementQuickQuantity(art)" :aria-label="`Sumar ${art.nombre}`">+</button>
                  </div>
                  <p class="mt-1 min-h-4 text-[11px] font-semibold text-gray-500">{{ quickQuantityHelper(art) }}</p>
                </div>

                <!-- Botón de agregar/actualizar carrito -->
                <button 
                  v-if="art.mostrar_precio && art.precio_lista"
                  @click="quickAddToCart(art)" 
                  class="ui-button ui-button-primary px-4 py-2.5 text-sm shadow-sm"
                >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    <span>{{ isInCart(art) ? 'Actualizar' : 'Agregar' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Vista detalle -->
        <div v-else-if="articulos.length > 0" class="space-y-3">
          <article
            v-for="art in articulos"
            :key="art.clave"
            :class="[
              'overflow-hidden rounded-lg border shadow-sm transition hover:border-red-200 hover:shadow-md',
              art.discontinuado === 'S' ? 'border-yellow-300 bg-yellow-50' : '',
              art.oferta === 'S' ? 'border-green-300 bg-green-50' : '',
              (art.discontinuado !== 'S' && art.oferta !== 'S') ? 'border-gray-200 bg-white' : ''
            ]"
          >
            <div class="flex flex-col gap-4 p-4 xl:flex-row xl:items-center">
              <div class="relative h-40 overflow-hidden rounded-lg border border-gray-200 bg-gray-100 xl:h-28 xl:w-32 xl:flex-shrink-0">
                <img
                  v-if="art.imagen"
                  :src="art.imagen"
                  :alt="art.nombre"
                  class="h-full w-full cursor-pointer object-contain p-3"
                  @click="openImageModal(art)"
                />
                <div
                  v-else
                  class="flex h-full w-full items-center justify-center px-4 text-center text-sm text-gray-400"
                  @click="showNotification('No hay imagen disponible', 'info')"
                >
                  Sin imagen
                </div>
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div class="min-w-0">
                    <div class="mb-2 flex flex-wrap gap-2">
                      <span v-if="art.discontinuado === 'S'" class="rounded-full bg-yellow-500 px-3 py-1 text-xs font-semibold text-white">
                        Discontinuado
                      </span>
                      <span v-if="art.oferta === 'S'" class="rounded-full bg-green-600 px-3 py-1 text-xs font-semibold text-white">
                        Oferta
                      </span>
                    </div>

                    <h3 class="text-lg font-bold text-gray-900" v-html="highlightMatch(art.nombre)"></h3>
                    <p class="mt-1 text-sm text-gray-500">
                      Clave:
                      <span class="font-semibold text-gray-800" v-html="highlightMatch(art.clave)"></span>
                    </p>
                    <p v-if="art.oferta === 'S' && getOfferExpiry(art)" class="mt-2 text-sm font-semibold text-green-800">
                      Vence: {{ formatDate(getOfferExpiry(art)) }}
                    </p>
                  </div>

                  <button
                    @click.stop="toggleFavorite(art)"
                    class="self-start rounded-full p-1 text-gray-400 transition-colors duration-200 hover:text-red-500 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                    :class="{ 'text-red-500': art.is_favorito }"
                    aria-label="Añadir o quitar de favoritos"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" :class="{ 'fill-current': art.is_favorito }" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                    </svg>
                  </button>
                </div>

                <div class="mt-4 grid grid-cols-2 gap-3 text-sm lg:grid-cols-5">
                  <div>
                    <p class="text-gray-500">Unidad</p>
                    <p class="font-semibold text-gray-900">{{ art.unidad }}</p>
                  </div>
                  <div>
                    <p class="text-gray-500">Peso</p>
                    <p class="font-semibold text-gray-900">{{ art.peso }}</p>
                  </div>
                  <div v-if="art.mts2 && parseFloat(art.mts2) > 0">
                    <p class="text-gray-500">Mts² por caja</p>
                    <p class="font-semibold text-blue-600">{{ formatCurrency(art.mts2) }} m²</p>
                  </div>
                  <div v-else>
                    <p class="text-gray-500">IVA</p>
                    <p class="font-semibold text-gray-900">{{ art.iva }}%</p>
                  </div>
                  <div>
                    <p class="text-gray-500">Últ. Act.</p>
                    <p class="font-semibold text-gray-900">{{ formatDate(art.ultact) }}</p>
                  </div>
                  <div v-if="art.mts2 && parseFloat(art.mts2) > 0">
                    <p class="text-gray-500">IVA</p>
                    <p class="font-semibold text-gray-900">{{ art.iva }}%</p>
                  </div>
                  <div>
                    <p class="text-gray-500">Stock</p>
                    <p :class="art.oferta === 'S' ? 'font-bold text-green-700' : 'font-semibold text-gray-900'">
                      {{ formatStock(art.stock) }}
                    </p>
                  </div>
                </div>
              </div>

              <div class="xl:w-72 xl:flex-shrink-0">
                <div class="rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <div v-if="art.mostrar_precio && art.precio_lista">
                    <p class="text-sm text-gray-500">Precio</p>
                    <p class="mt-1 text-2xl font-bold text-red-500">$ {{ formatCurrency(art.precio_lista) }}</p>
                  </div>
                  <div v-else>
                    <button
                      @click="consultarPrecio(art)"
                      :disabled="art.consultandoPrecio"
                      :class="art.consultandoPrecio ? 'bg-gray-400 cursor-not-allowed' : 'border border-blue-200 bg-blue-50 text-blue-800 hover:bg-blue-100'"
                      class="ui-button w-full px-3 py-2 text-sm"
                    >
                      <div v-if="art.consultandoPrecio" class="h-4 w-4 animate-spin rounded-full border-2 border-blue-700 border-t-transparent"></div>
                      <span v-if="art.consultandoPrecio">Consultando...</span>
                      <span v-else>Ver precio</span>
                    </button>
                  </div>

                  <div v-if="art.mostrar_precio && art.precio_lista" class="mt-3">
                    <div class="grid grid-cols-[40px_minmax(64px,1fr)_40px] overflow-hidden rounded-lg border border-gray-300 bg-white">
                      <button type="button" class="h-10 font-black text-gray-700 hover:bg-gray-100" @click="decrementQuickQuantity(art)">−</button>
                      <input type="number" :min="getQuickStep(art)" :step="getQuickStep(art)" :value="getQuickQuantity(art)" class="h-10 w-full border-x border-gray-200 text-center text-sm font-black focus:outline-none" @change="setQuickQuantity(art, $event.target.value)" />
                      <button type="button" class="h-10 font-black text-gray-700 hover:bg-gray-100" @click="incrementQuickQuantity(art)">+</button>
                    </div>
                    <p class="mt-1 text-[11px] font-semibold text-gray-500">{{ quickQuantityHelper(art) }}</p>
                  </div>

                  <button
                    v-if="art.mostrar_precio && art.precio_lista"
                    @click="quickAddToCart(art)"
                    class="ui-button ui-button-primary mt-3 w-full px-4 py-3 text-sm shadow-sm"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
                    </svg>
                    {{ isInCart(art) ? 'Actualizar pedido' : 'Agregar al pedido' }}
                  </button>
                </div>
              </div>
            </div>
          </article>
        </div>

        <!-- Sin resultados -->
        <EmptyState
          v-else-if="!loading"
          title="No se encontraron artículos"
          description="Probá con otra clave, limpiá la búsqueda o revisá los filtros activos."
        >
          <template #actions>
            <ActionButton type="button" variant="secondary" @click="clearSearch">
              Limpiar búsqueda
            </ActionButton>
          </template>
        </EmptyState>

        <!-- Paginación -->
        <div v-if="!loading && totalPages > 1" class="mt-6 flex flex-col gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm lg:flex-row lg:items-center lg:justify-between">
          <div class="text-sm text-gray-700">
            Página {{ currentPage }} de {{ totalPages }}. Mostrando {{ pageStartItem }}-{{ pageEndItem }} de {{ totalItems }} artículos.
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <button
              :disabled="currentPage === 1"
              @click="changePage(1)"
              class="rounded border border-gray-300 px-3 py-2 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-75"
            >
              Primero
            </button>
            <button
              :disabled="currentPage === 1"
              @click="changePage(currentPage - 1)"
              class="rounded border border-gray-300 px-4 py-2 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-75"
            >
              Anterior
            </button>
            <template v-for="item in paginationItems" :key="item.value">
              <span
                v-if="item.type === 'ellipsis'"
                class="px-2 py-2 text-sm font-medium text-gray-400"
              >
                ...
              </span>
              <button
                v-else
                @click="changePage(item.value)"
                class="rounded border px-3 py-2 text-sm font-medium transition"
                :class="item.value === currentPage ? 'border-red-600 bg-red-600 text-white' : 'border-gray-300 hover:bg-gray-100'"
              >
                {{ item.value }}
              </button>
            </template>
            <button
              :disabled="currentPage === totalPages"
              @click="changePage(currentPage + 1)"
              class="rounded border border-gray-300 px-4 py-2 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-75"
            >
              Siguiente
            </button>
            <button
              :disabled="currentPage === totalPages"
              @click="changePage(totalPages)"
              class="rounded border border-gray-300 px-3 py-2 hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-75"
            >
              Última
            </button>
          </div>
        </div>
        </div>

        <OrderSidebar v-model:collapsed="cartSidebarCollapsed" />
      </div>

      <QuickLoadPanel
        v-model:open="showQuickLoad"
        :modalidad="modalidad"
        :con-impuestos="conImpuestos"
        :condicion-pago="condicionPago"
        @added="showNotification($event, 'success')"
      />

      <!-- Modal de filtros (móvil) -->
      <div
        v-if="showMobileFilters && !isDesktop"
        class="fixed inset-0 z-50 flex flex-col bg-white"
      >
        <div class="flex justify-between items-center p-4 border-b bg-gray-50">
          <h3 class="text-lg font-medium text-gray-900">Filtros</h3>
          <button @click="closeFilterModal" class="text-gray-500 hover:text-gray-700">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-4 space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Condición de Pago</label>
            <select
              v-model="condicionPago"
              class="w-full px-3 py-2 border border-gray-300 rounded text-sm"
              :disabled="loadingFormasPago"
            >
              <option v-for="fp in formasPago" :key="fp.id" :value="fp.id">
                {{ fp.nombre }}
                <span v-if="fp.descuento > 0" class="text-red-600 text-xs">(-{{ fp.descuento }}%)</span>
                <span v-if="fp.punitorio > 0" class="text-red-600 text-xs">(punitorio +{{ fp.punitorio }}%)</span>
              </option>
            </select>
            <p v-if="loadingFormasPago" class="text-xs text-gray-500 mt-1">Cargando...</p>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Modalidad</label>
            <select v-model="modalidad" class="w-full px-3 py-2 border border-gray-300 rounded text-sm">
              <option value="retira">Retira</option>
              <option value="reparto">Reparto</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Precio</label>
            <select v-model="conImpuestos" class="w-full px-3 py-2 border border-gray-300 rounded text-sm">
              <option :value="true">Con impuestos</option>
              <option :value="false">Sin impuestos</option>
            </select>
          </div>
        </div>
        <div class="p-4 border-t bg-gray-50">
          <button
            @click="applyFilters"
            class="ui-button ui-button-primary w-full px-4 py-2 text-sm"
          >
            Aplicar filtros
          </button>
        </div>
      </div>

      <!-- Modal de imagen -->
      <div
        v-if="showImageModal && selectedArticulo"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
        @click="closeImageModal"
      >
        <div
          class="relative max-w-2xl w-full bg-white rounded-lg shadow-2xl p-6"
          @click.stop
        >
          <button
            @click="closeImageModal"
            class="absolute top-4 right-4 z-10 text-white bg-black/40 hover:bg-black/60 rounded-full p-2 transition"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <div class="flex flex-col items-center text-center">
            <img
              :src="selectedArticulo.imagen"
              :alt="'Imagen de ' + selectedArticulo.nombre"
              class="max-w-full max-h-96 object-contain rounded-lg border mb-4"
            />
            <h3 class="text-2xl font-bold text-gray-900">{{ selectedArticulo.nombre }}</h3>
            <p class="text-lg text-gray-600">Clave: {{ selectedArticulo.clave }}</p>
            <p class="text-base text-gray-500">Unidad: {{ selectedArticulo.unidad }} | Peso: {{ selectedArticulo.peso }} kg</p>
            <p class="text-xl font-semibold text-gray-800 mt-2">
              Precio: {{ formatCurrency(selectedArticulo.precio_lista) }}
            </p>
          </div>
        </div>
      </div>

      <!-- El modal de ofertas fue eliminado -->

      <!-- Toast Notifications -->
      <transition-group
        tag="div"
        name="toast"
        class="fixed top-4 right-4 space-y-2 z-50 max-w-sm w-full"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="{
            'bg-red-700': toast.type === 'error',
            'bg-red-600': toast.type === 'info',
            'bg-green-600': toast.type === 'success',
          }"
          class="px-5 py-3 rounded-lg shadow-lg text-white text-sm flex items-center gap-2 animate-in slide-in-from-top-2 duration-300"
          @click="removeToast(toast.id)"
        >
          <svg v-if="toast.type === 'error'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 20c-.77 1.333.192 3 1.732 3z" />
          </svg>

          <svg v-else-if="toast.type === 'success'" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
          </svg>

          <svg v-else class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>

          <span>{{ toast.message }}</span>
          <button class="ml-auto hover:bg-white/20 rounded p-1" @click.stop="removeToast(toast.id)">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </transition-group>

    <!-- Botón de Carrito Flotante (Arrastrable) -->
    <MobileOrderDrawer />

    <!-- Modal de Agregar al Carrito -->
    <div v-if="modalCarrito.visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-3 sm:p-4" @click.self="cerrarModalCarrito">
      <div class="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-2xl">
        <div class="flex items-start justify-between gap-4 border-b border-gray-200 px-5 py-4 sm:px-6">
          <div>
            <p class="text-xs font-bold uppercase tracking-wide text-red-700">Venta rápida</p>
            <h3 class="mt-1 text-xl font-bold text-gray-950 sm:text-2xl">Agregar al carrito</h3>
            <p class="mt-1 text-sm text-gray-600">Revisá la cantidad antes de confirmar.</p>
          </div>
          <button @click="cerrarModalCarrito" class="rounded-lg p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700" aria-label="Cerrar modal">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="overflow-y-auto px-5 py-5 sm:px-6">
          <!-- Información del Artículo -->
          <div class="rounded-lg border border-red-100 bg-red-50/70 p-4">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0">
                <p class="text-xs font-bold uppercase tracking-wide text-red-700">Producto seleccionado</p>
                <p class="mt-2 text-lg font-bold leading-snug text-gray-950">{{ modalCarrito.articulo?.nombre }}</p>
                <div class="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-gray-700">
                  <span class="rounded-md border border-gray-200 bg-white px-2.5 py-1">Clave {{ modalCarrito.articulo?.clave }}</span>
                  <span v-if="modalCarrito.tipo" class="rounded-md border border-gray-200 bg-white px-2.5 py-1">Tipo {{ modalCarrito.tipo }}</span>
                </div>
              </div>
              <div class="shrink-0 rounded-lg bg-white px-4 py-3 text-left shadow-sm sm:text-right">
                <p class="text-xs font-semibold uppercase text-gray-500">Precio lista</p>
                <p class="mt-1 text-2xl font-black text-red-700">${{ formatCurrency(modalCarrito.articulo?.precio_lista) }}</p>
              </div>
            </div>
          </div>

          <!-- Formulario según tipo de artículo -->
          <div class="mt-5 space-y-4">
            <!-- campoa1='c' o 'C': Artículos que se venden por peso (pero precio por cantidad) -->
            <div v-if="modalCarrito.articulo?.campoa1?.toLowerCase() === 'c'" class="rounded-lg border border-gray-200 bg-white p-4">
              <div class="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
                <p class="text-sm font-semibold text-blue-950">
                  Peso por artículo: {{ modalCarrito.articulo.peso }} kg
                </p>
                <p class="mt-1 text-xs text-blue-800">
                  Podés ingresar cantidad o peso total; el sistema calcula el otro dato.
                </p>
              </div>

              <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label class="block">
                  <span class="text-sm font-bold text-gray-800">Cantidad de artículos</span>
                  <input
                    v-model.number="modalCarrito.cantidad"
                    type="number"
                    min="1"
                    step="1"
                    class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                    placeholder="Ej: 10"
                  >
                </label>

                <label class="block">
                  <span class="text-sm font-bold text-gray-800">Peso total</span>
                  <input
                    v-model.number="modalCarrito.peso"
                    type="number"
                    min="0"
                    :step="modalCarrito.articulo.peso"
                    class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                    placeholder="Kg"
                  >
                </label>
              </div>

              <p class="mt-3 rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-700">
                <span class="font-semibold">Resumen:</span>
                <span class="font-bold text-gray-950">{{ modalCarrito.cantidad }} artículo(s)</span>
                =
                <span class="font-bold text-gray-950">{{ modalCarrito.peso }} kg</span>
              </p>
            </div>

            <!-- Tipo C o M (que NO sean campoa1='c'): Cantidad y Peso -->
            <div v-else-if="(modalCarrito.tipo === 'C' || modalCarrito.tipo === 'M') && modalCarrito.articulo?.campoa1?.toLowerCase() !== 'c'" class="rounded-lg border border-gray-200 bg-white p-4">
              <p class="mb-3 text-sm font-semibold text-gray-600">Completá cantidad y peso para calcular el total.</p>
              <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <label class="block">
                  <span class="text-sm font-bold text-gray-800">Cantidad</span>
                  <input
                    v-model.number="modalCarrito.cantidad"
                    type="number"
                    min="1"
                    step="1"
                    class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                    placeholder="Unidades"
                  >
                </label>

                <label class="block">
                  <span class="text-sm font-bold text-gray-800">Peso</span>
                  <input
                    v-model.number="modalCarrito.peso"
                    type="number"
                    min="0"
                    step="0.01"
                    class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                    placeholder="Kg"
                  >
                </label>
              </div>
            </div>

            <!-- Tipo A con mts2: Superficie -->
            <div v-if="modalCarrito.tipo === 'A' && modalCarrito.articulo?.mts2 > 0" class="rounded-lg border border-gray-200 bg-white p-4">
              <label class="block">
                <span class="text-sm font-bold text-gray-800">Superficie a cubrir</span>
                <input
                  v-model.number="modalCarrito.superficie"
                  @input="calcularCantidadPorSuperficie"
                  type="number"
                  min="0"
                  step="0.01"
                  class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                  placeholder="m2"
                >
              </label>

              <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div class="rounded-lg bg-gray-50 px-3 py-2">
                  <p class="text-xs font-semibold uppercase text-gray-500">m2 por caja</p>
                  <p class="text-lg font-bold text-gray-950">{{ modalCarrito.articulo.mts2 }}</p>
                </div>
                <div class="rounded-lg bg-gray-50 px-3 py-2">
                  <p class="text-xs font-semibold uppercase text-gray-500">Cajas necesarias</p>
                  <p class="text-lg font-bold text-gray-950">{{ modalCarrito.cantidad }}</p>
                </div>
              </div>
            </div>

            <!-- Tipo A sin mts2 o tipo normal -->
            <div v-if="(modalCarrito.tipo === 'A' && modalCarrito.articulo?.mts2 <= 0) || (!modalCarrito.tipo || (modalCarrito.tipo !== 'C' && modalCarrito.tipo !== 'M' && modalCarrito.tipo !== 'A'))" class="rounded-lg border border-gray-200 bg-white p-4">
              <label class="block">
                <span class="text-sm font-bold text-gray-800">Cantidad</span>
                <input
                  v-model.number="modalCarrito.cantidad"
                  type="number"
                  min="1"
                  step="1"
                  class="mt-1 w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-semibold text-gray-950 shadow-sm transition focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
                  placeholder="Unidades"
                >
              </label>
              <p class="mt-2 text-xs text-gray-500">Usá enteros para artículos por unidad.</p>
            </div>
          </div>
        </div>

        <div class="border-t border-gray-200 bg-gray-50 px-5 py-4 sm:px-6">
          <div class="mb-4 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-4 py-3">
            <div>
              <p class="text-xs font-semibold uppercase text-gray-500">Subtotal estimado</p>
              <p class="text-xs text-gray-500">Se confirma con las condiciones vigentes.</p>
            </div>
            <span class="text-2xl font-black text-gray-950">${{ formatCurrency(modalCarrito.subtotal) }}</span>
          </div>

          <div class="flex flex-col-reverse gap-3 sm:flex-row">
            <button
              @click="cerrarModalCarrito"
              class="inline-flex flex-1 items-center justify-center rounded-lg border border-gray-300 bg-white px-5 py-3 text-base font-bold text-gray-800 shadow-sm transition hover:border-gray-400 hover:bg-gray-100 focus:outline-none focus:ring-4 focus:ring-gray-200"
            >
              Cancelar
            </button>
            <button
              @click="agregarAlCarrito"
              :disabled="!modalCarrito.cantidad || modalCarrito.cantidad <= 0"
              class="inline-flex flex-1 items-center justify-center rounded-lg border border-red-700 bg-red-700 px-5 py-3 text-base font-bold text-white shadow-lg shadow-red-900/20 transition hover:border-red-800 hover:bg-red-800 focus:outline-none focus:ring-4 focus:ring-red-200 disabled:cursor-not-allowed disabled:border-gray-300 disabled:bg-gray-300 disabled:text-gray-600 disabled:shadow-none"
            >
              Agregar al carrito
            </button>
          </div>
        </div>
      </div>
    </div>

    </main>
  </div>
</template>

<style scoped>
:deep(.search-highlight) {
  border-radius: 4px;
  background: #fde68a;
  color: #7f1d1d;
  padding: 0 2px;
}

/* Altura fija para tarjetas */
.bg-white.rounded-lg.shadow {
  min-height: 420px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hover\\:scale-102:hover {
  transform: scale(1.02);
}

/* Animación suave para ofertas */
@keyframes gentle-pulse {
  0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.12); }
  50% { box-shadow: 0 8px 20px -6px rgba(34,197,94,0.18); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.12); }
}
.offer-animate {
  animation: gentle-pulse 3.5s ease-in-out infinite;
}
.offer-expiry {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(34,197,94,0.08);
  animation: gentle-pulse 4s ease-in-out infinite;
}

@media (max-width: 767px) {
  .main-content > .space-y-6 {
    gap: 10px;
  }

  .products-page-header {
    display: none;
  }

  .mobile-search-card {
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
  }

  .mobile-search-head {
    padding: 10px 12px;
  }

  .mobile-search-copy h2 {
    display: none;
  }

  .mobile-search-copy p:last-child {
    margin-top: 2px;
    font-size: 12px;
    line-height: 1.35;
  }

  .mobile-search-chips {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    padding-bottom: 2px;
    scrollbar-width: none;
  }

  .mobile-search-chips::-webkit-scrollbar {
    display: none;
  }

  .mobile-search-chips > * {
    flex: 0 0 auto;
    padding: 7px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }

  .mobile-search-body {
    padding: 10px 12px 12px;
  }

  .mobile-search-input input {
    height: 52px;
    min-width: 0;
    padding-left: 56px;
    font-size: 18px;
  }

  .mobile-search-input .h-9 {
    height: 36px;
    width: 36px;
  }

  .mobile-clear-button {
    height: 42px;
  }

  .products-view-toolbar {
    padding: 10px 12px;
  }

  .products-view-toolbar > div:first-child p:first-child {
    display: none;
  }

  .products-view-toolbar > div:last-child {
    display: none;
  }
}

/* Para truncar texto largo */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Animaciones para toast */
.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from, .toast-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
