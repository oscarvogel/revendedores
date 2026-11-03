<template>
  <div class="orders-page ui-page space-y-6">
    <PageHeader
      title="Mis pedidos"
      description="Seguimiento de pedidos, detalle de productos y acceso rápido para volver a pedir."
    >
      <template #actions>
        <ActionButton to="/productos" variant="secondary">
          Nuevo pedido
        </ActionButton>
        <button
          @click="cargarPedidos"
          :disabled="loading"
          class="inline-flex items-center justify-center rounded-lg border border-red-700 bg-red-700 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
        <svg v-if="loading" class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        {{ loading ? 'Cargando...' : 'Actualizar' }}
      </button>
      </template>
    </PageHeader>

    <!-- Filtros -->
    <div class="orders-filter-card rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <label class="block text-xs font-bold uppercase text-gray-500 mb-1">Estado del pedido</label>
          <select
            v-model="filtroEstado"
            @change="aplicarFiltros"
            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-sm font-semibold text-gray-950 shadow-sm focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100 sm:w-72"
          >
            <option value="">Todos los estados</option>
            <option value="PENDIENTE">Pendiente de revisión</option>
            <option value="CONFIRMADO">Confirmado</option>
            <option value="REVISADO">Revisado</option>
            <option value="CARGADO_ERP">Cargado en ERP</option>
            <option value="EN_PROCESO">En preparación</option>
            <option value="PREPARADO">Preparado</option>
            <option value="ENVIADO">Enviado</option>
            <option value="LISTO_RETIRO">Listo para retirar</option>
            <option value="ENTREGADO">Entregado</option>
            <option value="CANCELADO">Cancelado</option>
          </select>
        </div>
        
        <!-- Resumen rápido -->
        <div v-if="resumen" class="grid grid-cols-3 gap-2 text-sm sm:min-w-[460px]">
          <div class="rounded-lg bg-gray-50 px-3 py-2">
            <p class="text-xs font-semibold uppercase text-gray-500">Total</p>
            <p class="text-lg font-black text-gray-950">{{ resumen.total_pedidos }}</p>
          </div>
          <div class="rounded-lg bg-amber-50 px-3 py-2">
            <p class="text-xs font-semibold uppercase text-amber-700">Pendientes</p>
            <p class="text-lg font-black text-amber-900">{{ resumen.pedidos_pendientes }}</p>
          </div>
          <div class="rounded-lg bg-green-50 px-3 py-2">
            <p class="text-xs font-semibold uppercase text-green-700">Confirmados</p>
            <p class="text-lg font-black text-green-900">{{ resumen.pedidos_confirmados }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Estado de carga -->
    <LoadingState v-if="loading && pedidos.length === 0" label="Cargando pedidos..." />

    <!-- Sin pedidos -->
    <EmptyState
      v-else-if="!loading && pedidos.length === 0"
      title="No tenés pedidos todavía"
      description="Explorá productos y armá tu primer pedido desde el catálogo."
    >
      <template #actions>
        <ActionButton to="/productos">Ver productos</ActionButton>
      </template>
    </EmptyState>

    <!-- Lista de pedidos -->
    <div v-else class="space-y-4">
      <div v-for="pedido in pedidos" :key="pedido.id" class="order-card rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div class="min-w-0">
            <div class="mb-2 flex flex-wrap items-center gap-3">
              <p class="text-xs font-bold uppercase text-red-700">Pedido</p>
              <span :class="getEstadoClasses(pedido.estado)">
                {{ getEstadoTexto(pedido.estado) }}
              </span>
            </div>
            <h3 class="text-2xl font-black text-gray-950">#{{ pedido.id }}</h3>
            <p class="mt-1 text-sm font-semibold text-gray-500">{{ formatDate(pedido.fecha_creacion) }}</p>
          </div>
          <div class="rounded-lg bg-red-50 px-4 py-3 text-left lg:text-right">
            <p class="text-xs font-bold uppercase text-red-700">Total pedido</p>
            <p class="mt-1 text-2xl font-black text-gray-950">${{ formatCurrency(pedido.total) }}</p>
            <p class="mt-1 text-xs font-semibold text-gray-500">{{ pedido.items.length }} artículo{{ pedido.items.length !== 1 ? 's' : '' }}</p>
          </div>
        </div>

        <!-- Items del pedido -->
        <div class="mt-5 border-t border-gray-200 pt-4">
          <div class="mb-3 flex items-center justify-between gap-3">
            <h4 class="text-sm font-bold uppercase text-gray-500">
              Productos incluidos
            </h4>
            <p class="text-sm font-semibold text-gray-500">{{ getTotalCantidad(pedido.items) }} unidades</p>
          </div>
          <div class="grid grid-cols-1 gap-3 xl:grid-cols-2 2xl:grid-cols-3">
            <div v-for="item in previewItems(pedido.items)" :key="item.id" class="order-item flex items-center gap-3 rounded-lg border border-gray-200 bg-gray-50 p-3">
              <img
                :src="getArticuloImagen(item)"
                :alt="getArticuloNombre(item)"
                class="h-12 w-12 rounded-lg border border-gray-200 bg-white object-contain"
              >
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-bold text-gray-950">{{ getArticuloNombre(item) }}</p>
                <p class="mt-1 text-xs font-semibold text-gray-500">{{ item.cantidad }} x ${{ formatCurrency(item.precio_unitario) }}</p>
              </div>
              <div class="text-right text-sm font-black text-gray-950">
                ${{ formatCurrency(item.subtotal) }}
              </div>
            </div>
            <div v-if="pedido.items.length > 6" class="flex items-center justify-center rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 text-sm font-bold text-gray-500">
              +{{ pedido.items.length - 6 }} productos más
            </div>
          </div>
        </div>

        <!-- Acciones -->
        <div class="mt-5 flex flex-col gap-2 border-t border-gray-200 pt-4 sm:flex-row sm:justify-end">
          <button
            @click="verDetalle(pedido)"
            class="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-bold text-gray-800 shadow-sm transition hover:bg-gray-100"
          >
            Ver detalle
          </button>
          <button
            v-if="canReorder(pedido)"
            @click="reordenar(pedido)"
            class="inline-flex items-center justify-center rounded-lg border border-red-700 bg-red-700 px-5 py-3 text-sm font-black text-white shadow-lg shadow-red-900/20 transition hover:bg-red-800"
          >
            Repetir pedido
          </button>
        </div>
      </div>
    </div>

    <!-- Notificaciones -->
    <div v-if="notification.message" :class="notificationClasses" class="fixed top-4 right-4 max-w-sm w-full px-5 py-3 rounded-lg shadow-lg text-white text-sm flex items-center justify-between gap-2 z-50">
      <span>{{ notification.message }}</span>
      <button @click="notification = { message: '', type: '' }" class="text-white hover:text-gray-200 flex-shrink-0">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>

    <!-- Modal de Detalle del Pedido -->
    <div v-if="modalDetalle.show" class="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-3 sm:p-4" @click="cerrarModal">
      <div class="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-lg bg-white shadow-2xl" @click.stop>
        <!-- Header del Modal -->
        <div class="flex items-start justify-between gap-4 border-b border-gray-200 px-5 py-4 sm:px-6">
          <div>
            <p class="text-xs font-bold uppercase text-red-700">Detalle de pedido</p>
            <h3 class="mt-1 text-2xl font-black text-gray-950">
              Pedido #{{ modalDetalle.pedido?.id }}
            </h3>
            <p v-if="modalDetalle.pedido" class="mt-1 text-sm font-semibold text-gray-500">{{ formatDate(modalDetalle.pedido.fecha_creacion) }}</p>
          </div>
          <button @click="cerrarModal" class="rounded-lg p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700" aria-label="Cerrar detalle">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>

        <!-- Contenido del Modal -->
        <div v-if="modalDetalle.pedido" class="max-h-[calc(92vh-82px)] overflow-y-auto px-5 py-5 sm:px-6">
          <!-- Información General -->
          <div class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div class="rounded-lg border border-red-100 bg-red-50 p-4">
              <p class="text-xs font-bold uppercase text-red-700">Total</p>
              <p class="mt-1 text-3xl font-black text-gray-950">${{ formatCurrency(modalDetalle.pedido.total) }}</p>
            </div>
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p class="text-xs font-bold uppercase text-gray-500">Estado</p>
              <div class="mt-2">
                <span :class="getEstadoClasses(modalDetalle.pedido.estado)">
                  {{ getEstadoTexto(modalDetalle.pedido.estado) }}
                </span>
              </div>
            </div>
            <div class="rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p class="text-xs font-bold uppercase text-gray-500">Resumen</p>
              <p class="mt-1 text-lg font-black text-gray-950">{{ modalDetalle.pedido.items?.length || 0 }} artículos</p>
              <p class="text-sm font-semibold text-gray-500">{{ getTotalCantidad(modalDetalle.pedido.items) }} unidades</p>
            </div>
          </div>

          <!-- Lista Detallada de Productos -->
          <div class="mb-6">
            <h4 class="mb-3 text-sm font-bold uppercase text-gray-500">Productos del pedido</h4>
            <div class="overflow-hidden rounded-lg border border-gray-200">
              <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="px-4 py-3 text-left text-xs font-bold uppercase text-gray-500">Producto</th>
                    <th class="px-4 py-3 text-right text-xs font-bold uppercase text-gray-500">Precio unit.</th>
                    <th class="px-4 py-3 text-right text-xs font-bold uppercase text-gray-500">Cantidad</th>
                    <th class="px-4 py-3 text-right text-xs font-bold uppercase text-gray-500">Subtotal</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-gray-100 bg-white">
                  <tr v-for="item in modalDetalle.pedido.items" :key="item.id">
                    <td class="px-4 py-4">
                      <div class="flex items-center gap-3">
                        <img
                          class="h-12 w-12 rounded-lg border border-gray-200 bg-white object-contain"
                          :src="getArticuloImagen(item)"
                          :alt="getArticuloNombre(item)"
                        >
                        <div class="min-w-0">
                          <div class="truncate text-sm font-bold text-gray-950">{{ getArticuloNombre(item) }}</div>
                          <div class="text-xs font-semibold text-gray-500">
                            Clave {{ getArticuloClave(item) }}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td class="px-4 py-4 text-right text-sm font-semibold text-gray-900">
                      ${{ formatCurrency(item.precio_unitario) }}
                    </td>
                    <td class="px-4 py-4 text-right text-sm font-semibold text-gray-900">
                      {{ item.cantidad }}
                    </td>
                    <td class="px-4 py-4 text-right text-sm font-black text-gray-950">
                      ${{ formatCurrency(item.subtotal) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Acciones del Modal -->
          <div class="flex flex-col-reverse gap-3 border-t border-gray-200 pt-4 sm:flex-row sm:justify-end">
            <button
              @click="cerrarModal"
              class="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-5 py-3 text-sm font-bold text-gray-800 shadow-sm transition hover:bg-gray-100"
            >
              Cerrar
            </button>
            <button
              v-if="canReorder(modalDetalle.pedido)"
              @click="reordenar(modalDetalle.pedido); cerrarModal()"
              class="inline-flex items-center justify-center rounded-lg border border-red-700 bg-red-700 px-5 py-3 text-sm font-black text-white shadow-lg shadow-red-900/20 transition hover:bg-red-800"
            >
              Repetir pedido
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import api from '../services/api';
import { cart } from '../services/cart';
import ActionButton from '@/components/ui/ActionButton.vue';
import EmptyState from '@/components/ui/EmptyState.vue';
import LoadingState from '@/components/ui/LoadingState.vue';
import PageHeader from '@/components/ui/PageHeader.vue';

const router = useRouter();
const loading = ref(false);
const pedidos = ref([]);
const resumen = ref(null);
const filtroEstado = ref('');
const notification = ref({ message: '', type: '' });
const modalDetalle = ref({ show: false, pedido: null });

const notificationClasses = computed(() => ({
  'bg-green-600': notification.value.type === 'success',
  'bg-red-700': notification.value.type === 'error',
  'bg-blue-600': notification.value.type === 'info',
}));

const showNotification = (message, type) => {
  notification.value = { message, type };
  setTimeout(() => {
    notification.value = { message: '', type: '' };
  }, 4000);
};

const formatCurrency = (value) => {
  const number = parseFloat(value);
  if (isNaN(number)) return value;
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
};

const formatDate = (dateString) => {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('es-ES', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

const getEstadoClasses = (estado) => {
  const baseClasses = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium';
  
  switch (estado) {
    case 'PENDIENTE':
      return `${baseClasses} bg-yellow-100 text-yellow-800`;
    case 'CONFIRMADO':
      return `${baseClasses} bg-blue-100 text-blue-800`;
    case 'EN_PROCESO':
      return `${baseClasses} bg-purple-100 text-purple-800`;
    case 'PREPARADO':
      return `${baseClasses} bg-indigo-100 text-indigo-800`;
    case 'ENVIADO':
      return `${baseClasses} bg-orange-100 text-orange-800`;
    case 'ENTREGADO':
      return `${baseClasses} bg-green-100 text-green-800`;
    case 'CANCELADO':
      return `${baseClasses} bg-red-100 text-red-800`;
    default:
      return `${baseClasses} bg-gray-100 text-gray-800`;
  }
};

const getEstadoTexto = (estado) => {
  const estados = {
    'PENDIENTE': 'Pendiente de revisión',
    'REVISADO': 'Revisado',
    'CARGADO_ERP': 'Cargado en ERP',
    'LISTO_RETIRO': 'Listo para retirar',
    'CONFIRMADO': 'Confirmado',
    'EN_PROCESO': 'En preparación',
    'PREPARADO': 'Preparado',
    'ENVIADO': 'Enviado',
    'ENTREGADO': 'Entregado',
    'CANCELADO': 'Cancelado'
  };
  return estados[estado] || estado;
};

const getArticuloNombre = (item) => {
  // Manejar tanto el formato nuevo (articulo_detalle) como el antiguo (articulo)
  return item.articulo_detalle?.nombre || item.articulo?.nombre || 'Producto sin nombre';
};

const getArticuloClave = (item) => {
  if (item.articulo_detalle?.clave) return item.articulo_detalle.clave;
  if (item.articulo?.clave) return item.articulo.clave;
  return item.articulo || 'N/A';
};

const getArticuloImagen = (item) => {
  // Manejar tanto el formato nuevo (articulo_detalle) como el antiguo (articulo)
  return item.articulo_detalle?.imagen || item.articulo?.imagen || '/placeholder.png';
};

const previewItems = (items = []) => {
  return items.slice(0, 6);
};

const canReorder = (pedido) => {
  return pedido?.items?.length > 0 && pedido.estado !== 'CANCELADO';
};

const cargarPedidos = async () => {
  loading.value = true;
  try {
    console.log('🔄 Cargando pedidos...');
    
    // Cargar pedidos con filtro
    const params = {};
    if (filtroEstado.value) {
      params.estado = filtroEstado.value;
    }
    
    const response = await api.get('/api/pedidos/', { params });
    pedidos.value = response.data;
    console.log('✅ Pedidos cargados:', pedidos.value.length);
    
    // Cargar resumen
    const resumenResponse = await api.get('/api/pedidos/mis_pedidos_resumen/');
    resumen.value = resumenResponse.data;
    console.log('📊 Resumen cargado:', resumen.value);
    
  } catch (error) {
    console.error('❌ Error al cargar pedidos:', error);
    showNotification('Error al cargar los pedidos. Intenta nuevamente.', 'error');
  } finally {
    loading.value = false;
  }
};

const aplicarFiltros = () => {
  cargarPedidos();
};

const verDetalle = (pedido) => {
  modalDetalle.value = { show: true, pedido: pedido };
  console.log('Abriendo modal para pedido:', pedido);
};

const cerrarModal = () => {
  modalDetalle.value = { show: false, pedido: null };
};

const getTotalCantidad = (items) => {
  if (!items) return 0;
  return items.reduce((total, item) => total + (Number(item.cantidad) || 0), 0);
};

const reordenar = async (pedido) => {
  try {
    console.log('🛒 Agregando productos del pedido al carrito...');
    const modalidad = localStorage.getItem('articulos_modalidad') || 'retira';
    const conImpuestos = localStorage.getItem('articulos_con_impuestos') !== 'false';
    const condicion = localStorage.getItem('condicion_pago');
    const articulos = await Promise.all(pedido.items.map(async item => {
      const clave = item.articulo_detalle?.clave || item.articulo;
      const [articulo, precio] = await Promise.all([
        api.get(`/api/articulos/${encodeURIComponent(clave)}/`),
        api.post('/api/consultar-precio/', {
          articulo_clave: clave, modalidad, con_impuestos: conImpuestos,
          ...(condicion ? { condicion_pago: condicion } : {}),
        }),
      ]);
      const precioLista = Number(precio.data?.articulo?.precio_lista);
      if (!precio.data?.success || !Number.isFinite(precioLista) || precioLista <= 0) throw new Error(`Precio no disponible para ${clave}`);
      return { articulo: { ...articulo.data, precio_lista: precioLista }, cantidad: Number(item.cantidad) };
    }));

    // Conservar el carrito anterior si no se pueden recuperar todos los artículos.
    cart.clear();
    articulos.forEach(item => cart.add(item.articulo, item.cantidad));
    
    showNotification(`${pedido.items.length} productos agregados al carrito`, 'success');
    
    // Navegar al carrito
    setTimeout(() => {
      router.push('/carrito');
    }, 1000);
    
  } catch (error) {
    console.error('Error al reordenar:', error);
    showNotification('Error al agregar productos al carrito', 'error');
  }
};

onMounted(() => {
  cargarPedidos();
});
</script>

<style scoped>
.orders-page {
  padding-bottom: 32px;
}

.orders-filter-card,
.order-card {
  box-shadow: 0 14px 35px rgba(15, 23, 42, 0.07);
}

.orders-filter-card {
  border-left: 5px solid #c81e1e;
}

.order-card {
  position: relative;
  overflow: hidden;
}

.order-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #c81e1e;
}

.order-card,
.order-item {
  transition: box-shadow 0.15s ease, transform 0.15s ease, background-color 0.15s ease;
}

.order-card:hover {
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.1);
}

.order-item:hover {
  background: #fff7f7;
}
</style>
