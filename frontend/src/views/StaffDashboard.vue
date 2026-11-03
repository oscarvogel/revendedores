<template>
  <div class="min-h-screen bg-gray-50 px-4 py-5 font-sans sm:px-6 lg:px-8">
    <div class="mx-auto max-w-7xl space-y-5">
    <!-- Encabezado -->
    <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm sm:p-5">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p class="text-xs font-semibold uppercase tracking-wide text-red-700">Panel interno</p>
          <h1 class="mt-1 text-3xl font-bold text-gray-950 sm:text-4xl">Staff Dashboard</h1>
          <p class="mt-2 max-w-3xl text-sm text-gray-600">
            Monitoreá actividad, pedidos, clientes y consultas desde una vista ordenada por áreas.
          </p>
        </div>
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center lg:justify-end">
          <p v-if="lastUpdated" class="last-updated">
            Última actualización: {{ lastUpdated }}
          </p>
          <button
            @click="reloadData"
            :disabled="loading"
            class="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-red-700 disabled:bg-gray-400"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-4 w-4"
              :class="{ 'animate-spin': loading }"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {{ loading ? 'Recargando...' : 'Recargar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Filtro Global por Usuario -->
    <div class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div class="flex flex-col gap-4">
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.207A1 1 0 013 6.5V4z" />
          </svg>
          <label class="text-sm font-medium text-gray-700">Filtrar por Usuario:</label>
        </div>
        
        <div class="relative flex-1">
          <div class="flex gap-2">
            <div class="relative flex-1">
              <input
                v-model="usuariosBusqueda"
                @input="onUsuarioBusquedaInput"
                @focus="mostrarSugerenciasUsuarios = listaUsuarios.length > 0"
                placeholder="Buscar por username, nombre o email..."
                class="w-full rounded-lg border border-gray-300 px-3 py-2 pr-10 text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-red-500"
                autocomplete="off"
              />
              
              <!-- Loading indicator -->
              <div v-if="loadingUsuarios" class="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div class="animate-spin h-4 w-4 border-2 border-gray-300 border-t-red-500 rounded-full"></div>
              </div>
              
              <!-- Search icon -->
              <div v-else class="absolute right-3 top-1/2 transform -translate-y-1/2">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              
              <!-- Dropdown de sugerencias -->
              <div 
                v-if="mostrarSugerenciasUsuarios && listaUsuarios.length > 0"
                class="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto"
              >
                <div
                  v-for="usuario in listaUsuarios"
                  :key="usuario.id"
                  @click="seleccionarUsuario(usuario)"
                  class="px-4 py-3 hover:bg-gray-50 cursor-pointer border-b last:border-b-0"
                >
                  <div class="flex items-center justify-between">
                    <div>
                      <div class="font-medium text-gray-900">{{ usuario.username }}</div>
                      <div class="text-sm text-gray-500">
                        {{ usuario.nombre_completo || `${usuario.first_name} ${usuario.last_name}` }}
                      </div>
                      <div v-if="usuario.cliente_nombre" class="text-xs text-blue-600">
                        Cliente: {{ usuario.cliente_nombre }}
                      </div>
                    </div>
                    <div class="text-xs text-gray-400">
                      {{ usuario.email }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <button 
              v-if="filtroUsuarioGlobal"
              @click="limpiarFiltroUsuario"
              class="flex items-center gap-1 rounded-lg bg-gray-700 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-800"
              title="Limpiar filtro"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Limpiar
            </button>
          </div>
        </div>
        
        <div v-if="filtroUsuarioGlobal" class="flex items-center gap-2 text-sm">
          <div class="bg-blue-50 text-blue-800 px-3 py-1 rounded-full flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span><strong>Filtro activo:</strong> {{ filtroUsuarioGlobal }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Tarjetas de Resumen -->
    <section class="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <!-- Total de Pedidos -->
      <div class="staff-metric-card">
        <h3>Total de Pedidos</h3>
        <p class="text-red-600">{{ salesSummary.total_orders }}</p>
      </div>

      <!-- Ventas Totales -->
      <div class="staff-metric-card">
        <h3>Ventas Totales</h3>
        <p class="text-green-600">${{ formatCurrency(salesSummary.total_sales) }}</p>
      </div>

      <!-- Ventas Últimos 30 Días -->
      <div class="staff-metric-card">
        <h3>Últimos 30 Días</h3>
        <p class="text-blue-600">${{ formatCurrency(salesSummary.sales_last_30_days) }}</p>
      </div>

      <!-- Ingresos (Sesiones) -->
      <div 
        @click="mostrarIngresosHoy"
        class="staff-metric-card cursor-pointer hover:border-purple-300 hover:shadow-md"
      >
        <h3>Ingresos Hoy</h3>
        <p class="text-purple-600">{{ sessionMetrics.sessionsToday }}</p>
        <span class="mt-2 block text-xs text-gray-500">Ver detalle</span>
      </div>

      <!-- Tiempo Promedio -->
      <div class="staff-metric-card">
        <h3>Tiempo Promedio</h3>
        <p class="text-orange-600">{{ sessionMetrics.avgDuration }}</p>
      </div>
    </section>

    <nav class="staff-tabs" aria-label="Secciones del dashboard staff">
      <button
        v-for="tab in staffTabs"
        :key="tab.id"
        type="button"
        class="staff-tab"
        :class="{ 'staff-tab-active': activeStaffTab === tab.id }"
        @click="activeStaffTab = tab.id"
      >
        <span>{{ tab.label }}</span>
        <small>{{ tab.description }}</small>
      </button>
    </nav>

    <div v-show="activeStaffTab === 'actividad'" class="staff-tab-panel">
    <!-- Resumen: Descargas / Exportaciones por Cliente -->
    <section class="staff-panel">
      <div class="flex justify-between items-center mb-4">
        <h2 class="staff-section-title">Descargas por Cliente</h2>
        <div class="flex items-center gap-2">
          <button
            @click="fetchExportsSummary"
            :disabled="loadingExportsSummary"
            class="px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 transition disabled:opacity-60"
          >
            {{ loadingExportsSummary ? 'Cargando...' : 'Actualizar' }}
          </button>
        </div>
      </div>

      <div v-if="loadingExportsSummary" class="text-center py-6">
        <div class="animate-spin inline-block w-8 h-8 border-4 border-yellow-500 border-t-transparent rounded-full"></div>
        <p class="mt-2 text-gray-600">Cargando resumen de descargas...</p>
      </div>

      <div v-else-if="exportsSummary.length === 0" class="text-center py-6 text-gray-500">
        No hay registros de descargas disponibles.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-yellow-50 border-b">
              <th class="text-left py-3 px-4 font-medium text-gray-700">Cliente (Nº)</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Usuario</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Nombre</th>
              <th class="text-center py-3 px-4 font-medium text-gray-700">Veces descargada</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Última descarga</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in exportsSummary" :key="item.usuario_id" class="border-b hover:bg-gray-50">
              <td class="py-3 px-4 text-sm text-gray-800">{{ item.numero_cliente || '—' }}</td>
              <td class="py-3 px-4 text-sm font-medium text-gray-900">{{ item.username }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ item.nombre_cliente || (item.first_name + ' ' + item.last_name).trim() }}</td>
              <td class="py-3 px-4 text-center font-semibold text-yellow-700">{{ item.total_exports }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ item.last_export ? new Date(item.last_export).toLocaleString('es-AR') : '—' }}</td>
              <td class="py-3 px-4 text-right">
                <button
                  @click="openExportDetails(item)"
                  class="px-3 py-1 bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200 text-sm"
                >Ver resumen</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Modal: detalles de exportaciones (paginado) -->
      <div v-if="showExportDetailsModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
        <div class="bg-white rounded-lg w-full max-w-4xl overflow-hidden max-h-[80vh]">
          <div class="flex items-center justify-between p-4 border-b">
            <h3 class="text-lg font-semibold">Resumen de descargas — {{ exportDetailsUsuarioFiltro }}</h3>
            <div class="flex items-center gap-2">
              <button @click="closeExportDetails" class="px-3 py-1 text-sm border rounded">Cerrar</button>
            </div>
          </div>
          <div class="p-4 overflow-auto">
            <div v-if="loadingExportDetails" class="text-center py-6">
              <div class="animate-spin inline-block w-8 h-8 border-4 border-yellow-500 border-t-transparent rounded-full"></div>
              <p class="mt-2 text-gray-600">Cargando...</p>
            </div>

            <div v-else-if="exportDetails.length === 0" class="text-center py-6 text-gray-500">No hay registros para este usuario.</div>

            <div v-else class="overflow-x-auto">
              <table class="w-full border-collapse">
                <thead>
                  <tr class="bg-gray-50 border-b">
                    <th class="text-left py-2 px-3 text-sm">Fecha</th>
                    <th class="text-left py-2 px-3 text-sm">Parámetros</th>
                    <th class="text-center py-2 px-3 text-sm">Items</th>
                    <th class="text-left py-2 px-3 text-sm">IP</th>
                    <th class="text-left py-2 px-3 text-sm">User Agent</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="e in exportDetails" :key="e.id" class="border-b hover:bg-gray-50 align-top">
                    <td class="py-2 px-3 text-sm text-gray-700">{{ formatDateTime(e.fecha_hora) }}</td>
                    <td class="py-2 px-3 text-sm text-gray-700"><pre class="whitespace-pre-wrap text-xs">{{ prettyParams(e.parametros) }}</pre></td>
                    <td class="py-2 px-3 text-center font-semibold text-gray-800">{{ e.total_items }}</td>
                    <td class="py-2 px-3 text-sm text-gray-700">{{ e.ip_address || '—' }}</td>
                    <td class="py-2 px-3 text-sm text-gray-700 break-words">{{ e.user_agent || '—' }}</td>
                  </tr>
                </tbody>
              </table>

              <!-- Paginación simple -->
              <div class="flex items-center justify-between mt-4">
                <div class="text-sm text-gray-600">Mostrando página {{ exportDetailsPage }} de {{ exportDetailsTotalPages }} — {{ exportDetailsTotalItems }} registros</div>
                <div class="flex items-center gap-2">
                  <button :disabled="exportDetailsPage <= 1" @click="fetchExportDetails(exportDetailsPage - 1)" class="px-3 py-1 border rounded disabled:opacity-50">Anterior</button>
                  <select v-model.number="exportDetailsPage" @change="fetchExportDetails(exportDetailsPage)" class="px-2 py-1 border rounded">
                    <option v-for="p in exportDetailsTotalPages" :key="p" :value="p">{{ p }}</option>
                  </select>
                  <button :disabled="exportDetailsPage >= exportDetailsTotalPages" @click="fetchExportDetails(exportDetailsPage + 1)" class="px-3 py-1 border rounded disabled:opacity-50">Siguiente</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Resumen: Vistas de Ofertas y Discontinuados -->
    <section class="staff-panel">
      <div class="flex justify-between items-center mb-4">
        <h2 class="staff-section-title">Vistas de Ofertas y Discontinuados</h2>
        <div class="flex items-center gap-2">
          <button
            @click="fetchArticulosVistasSummary"
            :disabled="loadingArticulosVistasSummary"
            class="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition disabled:opacity-60"
          >
            {{ loadingArticulosVistasSummary ? 'Cargando...' : 'Actualizar' }}
          </button>
        </div>
      </div>

      <div v-if="loadingArticulosVistasSummary" class="text-center py-6">
        <div class="animate-spin inline-block w-8 h-8 border-4 border-green-500 border-t-transparent rounded-full"></div>
        <p class="mt-2 text-gray-600">Cargando vistas...</p>
      </div>

      <div v-else-if="articulosVistasSummary.length === 0" class="text-center py-6 text-gray-500">
        No hay registros de vistas disponibles.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse">
          <thead>
            <tr class="bg-green-50 border-b">
              <th class="text-left py-3 px-4 font-medium text-gray-700">Cliente (Nº)</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Usuario</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Nombre</th>
              <th class="text-center py-3 px-4 font-medium text-gray-700">Ofertas</th>
              <th class="text-center py-3 px-4 font-medium text-gray-700">Discontinuados</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Últ. Oferta</th>
              <th class="text-left py-3 px-4 font-medium text-gray-700">Últ. Discontinuado</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in articulosVistasSummary" :key="item.usuario_id" class="border-b hover:bg-gray-50">
              <td class="py-3 px-4 text-sm text-gray-800">{{ item.numero_cliente || '—' }}</td>
              <td class="py-3 px-4 text-sm font-medium text-gray-900">{{ item.username }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ item.nombre_cliente || (item.first_name + ' ' + item.last_name).trim() }}</td>
              <td class="py-3 px-4 text-center font-semibold text-green-700">{{ item.total_ofertas }}</td>
              <td class="py-3 px-4 text-center font-semibold text-red-700">{{ item.total_discontinuados }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ formatDateTime(item.last_oferta) }}</td>
              <td class="py-3 px-4 text-sm text-gray-600">{{ formatDateTime(item.last_discontinuado) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    </div>

    <div v-show="activeStaffTab === 'operacion'" class="staff-tab-panel">
    <!-- Sección de Gestión de Pedidos -->
    <section class="staff-panel">
      <div class="flex justify-between items-center mb-4">
        <div class="flex items-center gap-3">
          <h2 class="staff-section-title">Gestión de Pedidos</h2>
          <div v-if="filtroUsuarioGlobal" class="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
            🔍 Filtrado por: {{ filtroUsuarioGlobal }}
          </div>
        </div>
        <div class="flex gap-3">
          <button
            @click="togglePedidosView"
            :class="mostrarPedidos ? 'bg-red-600 text-white' : 'bg-gray-200 text-gray-700'"
            class="px-4 py-2 rounded-lg font-medium transition hover:bg-red-700 hover:text-white"
          >
            {{ mostrarPedidos ? 'Ocultar Pedidos' : 'Ver Todos los Pedidos' }}
          </button>
          <button
            @click="toggleClientesView"
            :class="mostrarClientes ? 'bg-green-600 text-white' : 'bg-gray-200 text-gray-700'"
            class="px-4 py-2 rounded-lg font-medium transition hover:bg-green-700 hover:text-white"
          >
            {{ mostrarClientes ? 'Ocultar Clientes' : 'Gestionar Clientes' }}
          </button>
          <button
            v-if="mostrarPedidos"
            @click="cargarTodosPedidos"
            :disabled="loadingPedidos"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            <svg v-if="loadingPedidos" class="animate-spin h-4 w-4 mr-2 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ loadingPedidos ? 'Cargando...' : 'Actualizar' }}
          </button>
          <button
            v-if="mostrarClientes"
            @click="cargarTodosClientes"
            :disabled="loadingClientes"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50"
          >
            <svg v-if="loadingClientes" class="animate-spin h-4 w-4 mr-2 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 818-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ loadingClientes ? 'Cargando...' : 'Actualizar' }}
          </button>
        </div>
      </div>

      <!-- Vista de Pedidos -->
      <div v-if="mostrarPedidos" class="mt-6">
        <!-- Filtros y Estadísticas Rápidas -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div class="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
            <h4 class="font-medium text-yellow-800">Pendientes</h4>
            <p class="text-2xl font-bold text-yellow-600">{{ resumenPedidos.pendientes || 0 }}</p>
          </div>
          <div class="bg-blue-50 p-4 rounded-lg border border-blue-200">
            <h4 class="font-medium text-blue-800">Confirmados</h4>
            <p class="text-2xl font-bold text-blue-600">{{ resumenPedidos.confirmados || 0 }}</p>
          </div>
          <div class="bg-purple-50 p-4 rounded-lg border border-purple-200">
            <h4 class="font-medium text-purple-800">En Proceso</h4>
            <p class="text-2xl font-bold text-purple-600">{{ resumenPedidos.en_proceso || 0 }}</p>
          </div>
          <div class="bg-green-50 p-4 rounded-lg border border-green-200">
            <h4 class="font-medium text-green-800">Entregados</h4>
            <p class="text-2xl font-bold text-green-600">{{ resumenPedidos.entregados || 0 }}</p>
          </div>
        </div>

        <!-- Filtros y Info de Paginación -->
        <div class="bg-gray-50 p-4 rounded-lg mb-6">
          <div class="flex flex-wrap gap-4 items-center justify-between">
            <!-- Filtros -->
            <div class="flex flex-wrap gap-4 items-center">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Estado:</label>
                <select 
                  v-model="filtroEstadoPedidos" 
                  @change="aplicarFiltrosPedidos"
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-red-500"
                >
                  <option value="">Todos</option>
                  <option value="PENDIENTE">Pendiente</option>
                  <option value="CONFIRMADO">Confirmado</option>
                  <option value="EN_PROCESO">En Proceso</option>
                  <option value="PREPARADO">Preparado</option>
                  <option value="ENVIADO">Enviado</option>
                  <option value="ENTREGADO">Entregado</option>
                  <option value="CANCELADO">Cancelado</option>
                </select>
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Usuario:</label>
                <input 
                  v-model="filtroUsuario"
                  @input="aplicarFiltrosPedidos"
                  type="text" 
                  placeholder="Buscar por usuario..."
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-red-500"
                >
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Fecha desde:</label>
                <input 
                  v-model="filtroFechaDesde"
                  @change="aplicarFiltrosPedidos"
                  type="date"
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-red-500"
                >
              </div>
            </div>
            
            <!-- Información de Paginación -->
            <div v-if="!loadingPedidos && paginacionPedidos.totalItems > 0" class="text-sm text-gray-600 bg-white px-3 py-2 rounded-md border">
              <div class="text-center">
                <div class="font-semibold text-gray-800">
                  {{ paginacionPedidos.totalItems }} pedidos encontrados
                </div>
                <div class="text-xs mt-1">
                  Página {{ paginacionPedidos.currentPage }} de {{ paginacionPedidos.totalPages }}
                  ({{ paginacionPedidos.pageSize }} por página)
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Lista de Pedidos -->
        <div v-if="loadingPedidos" class="flex justify-center py-8">
          <div class="text-center">
            <svg class="animate-spin h-8 w-8 text-red-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="mt-2 text-gray-600">Cargando pedidos...</p>
          </div>
        </div>

        <div v-else-if="pedidosFiltrados.length === 0" class="text-center py-8 text-gray-500">
          No se encontraron pedidos con los filtros aplicados.
        </div>

        <div v-else class="space-y-4">
          <div v-for="pedido in pedidosFiltrados" :key="pedido.id" class="bg-white border rounded-lg p-6 shadow-sm">
            <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between mb-4">
              <div class="flex items-center space-x-4 mb-2 lg:mb-0">
                <h3 class="text-lg font-semibold text-gray-900">Pedido #{{ pedido.id }}</h3>
                <select
                  :value="pedido.estado"
                  @change="cambiarEstadoPedido(pedido.id, $event.target.value)"
                  :class="getEstadoSelectClasses(pedido.estado)"
                  class="px-3 py-1 rounded-full text-xs font-medium border-0"
                >
                  <option value="PENDIENTE">Pendiente</option>
                  <option value="CONFIRMADO">Confirmado</option>
                  <option value="EN_PROCESO">En Proceso</option>
                  <option value="PREPARADO">Preparado</option>
                  <option value="ENVIADO">Enviado</option>
                  <option value="ENTREGADO">Entregado</option>
                  <option value="CANCELADO">Cancelado</option>
                </select>
              </div>
              <div class="text-sm text-gray-600 lg:text-right">
                <p><strong>Usuario:</strong> {{ pedido.usuario_nombre || pedido.user }}</p>
                <p><strong>Fecha:</strong> {{ formatDate(pedido.fecha_creacion) }}</p>
                <p class="font-semibold text-lg text-green-600">${{ formatCurrency(pedido.total) }}</p>
              </div>
            </div>

            <!-- Productos del pedido (resumido) -->
            <div class="border-t pt-4 mb-4">
              <p class="text-sm text-gray-600 mb-2">
                <strong>{{ pedido.items?.length || 0 }} productos</strong> - 
                {{ getTotalCantidadPedido(pedido.items) }} artículos
              </p>
              <div class="flex flex-wrap gap-2">
                <span 
                  v-for="item in (pedido.items || []).slice(0, 3)" 
                  :key="item.id"
                  class="inline-block bg-gray-100 px-2 py-1 rounded text-xs text-gray-700"
                >
                  {{ item.cantidad }}x {{ getArticuloNombrePedido(item) }}
                </span>
                <span 
                  v-if="(pedido.items || []).length > 3"
                  class="inline-block bg-gray-200 px-2 py-1 rounded text-xs text-gray-600"
                >
                  +{{ (pedido.items || []).length - 3 }} más
                </span>
              </div>
            </div>

            <!-- Acciones -->
            <div class="flex flex-wrap gap-2 pt-4 border-t">
              <button 
                @click="verDetallePedidoStaff(pedido)"
                class="flex items-center px-3 py-2 text-sm text-blue-600 bg-blue-50 rounded-md hover:bg-blue-100 transition duration-200"
              >
                <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                </svg>
                Ver Detalle
              </button>
              <button 
                @click="reenviarConfirmacion(pedido.id)"
                :disabled="enviandoEmail"
                class="flex items-center px-3 py-2 text-sm text-green-600 bg-green-50 rounded-md hover:bg-green-100 transition duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path>
                </svg>
                {{ enviandoEmail ? 'Enviando...' : 'Reenviar Email' }}
              </button>
              <button 
                @click="editarPedido(pedido)"
                class="flex items-center px-3 py-2 text-sm text-purple-600 bg-purple-50 rounded-md hover:bg-purple-100 transition duration-200"
              >
                <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                </svg>
                Editar
              </button>
              <button 
                v-if="pedido.estado !== 'CANCELADO'"
                @click="cancelarPedidoStaff(pedido.id)"
                class="flex items-center px-3 py-2 text-sm text-red-600 bg-red-50 rounded-md hover:bg-red-100 transition duration-200"
              >
                <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                Cancelar
              </button>
            </div>
          </div>
        </div>

        <!-- Información de paginación (siempre visible) -->
        <div v-if="pedidosFiltrados.length > 0" class="flex flex-col sm:flex-row justify-between items-center mt-6 space-y-4 sm:space-y-0 bg-gray-50 p-4 rounded-lg">
          <!-- Información de paginación -->
          <div class="text-sm text-gray-600">
            <div>
              Mostrando {{ (paginacionPedidos.currentPage - 1) * paginacionPedidos.pageSize + 1 }} - 
              {{ Math.min(paginacionPedidos.currentPage * paginacionPedidos.pageSize, paginacionPedidos.totalItems) }} 
              de {{ paginacionPedidos.totalItems }} pedidos
            </div>
            <div class="text-xs text-gray-500 mt-1">
              Página {{ paginacionPedidos.currentPage }} de {{ paginacionPedidos.totalPages }}
            </div>
          </div>

          <!-- Controles de paginación -->
          <div class="flex items-center space-x-2">
            <!-- Selector de tamaño de página -->
            <select 
              :value="paginacionPedidos.pageSize"
              @change="cambiarTamanoPagina($event.target.value)"
              class="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-red-500"
            >
              <option value="5">5 por página</option>
              <option value="10">10 por página</option>
              <option value="20">20 por página</option>
              <option value="50">50 por página</option>
            </select>

            <!-- Botones de navegación (solo si hay más de 1 página) -->
            <div v-if="paginacionPedidos.totalPages > 1" class="flex space-x-1">
              <button 
                @click="paginaAnterior"
                :disabled="!paginacionPedidos.hasPrevious"
                class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Anterior
              </button>

              <!-- Números de página -->
              <template v-for="page in getPaginasVisibles()" :key="page">
                <button 
                  v-if="page !== '...'"
                  @click="irAPagina(page)"
                  :class="[
                    'px-3 py-1 text-sm border rounded',
                    page === paginacionPedidos.currentPage 
                      ? 'bg-red-600 text-white border-red-600' 
                      : 'border-gray-300 hover:bg-gray-50'
                  ]"
                >
                  {{ page }}
                </button>
                <span v-else class="px-2 py-1 text-sm text-gray-500">...</span>
              </template>

              <button 
                @click="paginaSiguiente"
                :disabled="!paginacionPedidos.hasNext"
                class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Gestión de Clientes -->
    <section v-if="mostrarClientes" class="staff-panel">
      <div class="flex justify-between items-center mb-6">
        <h2 class="staff-section-title">Gestión de Clientes</h2>
        <button
          @click="abrirModalNuevoCliente"
          class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center"
        >
          <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path>
          </svg>
          Nuevo Cliente
        </button>
      </div>

      <div class="mb-6">
        <!-- Filtros de Clientes -->
        <div class="bg-gray-50 p-4 rounded-lg mb-6">
          <div class="flex flex-wrap gap-4 items-center justify-between">
            <!-- Filtros -->
            <div class="flex flex-wrap gap-4 items-center">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Nombre/Usuario:</label>
                <input 
                  v-model="filtroNombreCliente"
                  @input="aplicarFiltrosClientes"
                  type="text" 
                  placeholder="Buscar por nombre o usuario..."
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-green-500"
                >
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Número Cliente:</label>
                <input 
                  v-model="filtroNumeroCliente"
                  @input="aplicarFiltrosClientes"
                  type="text" 
                  placeholder="Número de cliente..."
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-green-500"
                >
              </div>
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Lista de Precio:</label>
                <select 
                  v-model="filtroListaPrecio" 
                  @change="aplicarFiltrosClientes"
                  class="border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-1 focus:ring-green-500"
                >
                  <option value="">Todas</option>
                  <option value="1">Lista 1</option>
                  <option value="4">Lista 4</option>
                </select>
              </div>
            </div>
            
            <!-- Información de Paginación -->
            <div v-if="!loadingClientes && paginacionClientes.totalItems > 0" class="text-sm text-gray-600 bg-white px-3 py-2 rounded-md border">
              <div class="text-center">
                <div class="font-semibold text-gray-800">
                  {{ paginacionClientes.totalItems }} clientes encontrados
                </div>
                <div class="text-xs mt-1">
                  Página {{ paginacionClientes.currentPage }} de {{ paginacionClientes.totalPages }}
                  ({{ paginacionClientes.pageSize }} por página)
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Lista de Clientes -->
        <div v-if="loadingClientes" class="flex justify-center py-8">
          <div class="text-center">
            <svg class="animate-spin h-8 w-8 text-green-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p class="mt-2 text-gray-600">Cargando clientes...</p>
          </div>
        </div>

        <div v-else-if="clientesFiltrados.length === 0" class="text-center py-8 text-gray-500">
          No se encontraron clientes con los filtros aplicados.
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full border-collapse">
            <thead>
              <tr class="bg-gray-50 border-b">
                <th class="text-left py-3 px-4 font-medium text-gray-700">Cliente</th>
                <th class="text-left py-3 px-4 font-medium text-gray-700">Usuario</th>
                <th class="text-left py-3 px-4 font-medium text-gray-700">Email</th>
                <th class="text-left py-3 px-4 font-medium text-gray-700">Lista</th>
                <th class="text-left py-3 px-4 font-medium text-gray-700">Localidad</th>
                <th class="text-left py-3 px-4 font-medium text-gray-700">Estado</th>
                <th class="text-center py-3 px-4 font-medium text-gray-700">Acciones</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cliente in clientesFiltrados" :key="cliente.id" class="border-b hover:bg-gray-50">
                <td class="py-3 px-4">
                  <div>
                    <div class="font-medium text-gray-900">{{ cliente.numero_cliente }}</div>
                    <div class="text-sm text-gray-600">{{ cliente.nombre }}</div>
                  </div>
                </td>
                <td class="py-3 px-4">
                  <div>
                    <div class="font-medium text-gray-900">{{ cliente.username }}</div>
                    <div class="text-sm text-gray-600">{{ cliente.first_name }} {{ cliente.last_name }}</div>
                  </div>
                </td>
                <td class="py-3 px-4 text-sm text-gray-600">{{ cliente.email }}</td>
                <td class="py-3 px-4">
                  <span class="inline-block px-2 py-1 text-xs rounded-full" :class="cliente.lista_precio === '1' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'">
                    Lista {{ cliente.lista_precio }}
                  </span>
                </td>
                <td class="py-3 px-4 text-sm text-gray-600">{{ cliente.localidad || 'N/A' }}</td>
                <td class="py-3 px-4">
                  <span class="inline-block px-2 py-1 text-xs rounded-full" :class="cliente.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'">
                    {{ cliente.is_active ? 'Activo' : 'Inactivo' }}
                  </span>
                </td>
                <td class="py-3 px-4">
                  <div class="flex justify-center space-x-2">
                    <button 
                      @click="verDetalleCliente(cliente)"
                      class="text-blue-600 hover:text-blue-800 transition"
                      title="Ver detalle"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
                      </svg>
                    </button>
                    <button 
                      @click="editarCliente(cliente)"
                      class="text-purple-600 hover:text-purple-800 transition"
                      title="Editar"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                      </svg>
                    </button>
                    <button 
                      @click="eliminarCliente(cliente)"
                      class="text-red-600 hover:text-red-800 transition"
                      title="Eliminar"
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                      </svg>
                    </button>
                    <button 
                      @click="toggleActivoCliente(cliente)"
                      :class="cliente.is_active ? 'text-orange-600 hover:text-orange-800' : 'text-green-600 hover:text-green-800'"
                      class="transition"
                      :title="cliente.is_active ? 'Desactivar' : 'Activar'"
                    >
                      <svg v-if="cliente.is_active" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                      </svg>
                      <svg v-else class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Paginación de Clientes -->
        <div v-if="!loadingClientes && clientesFiltrados.length > 0" class="flex flex-col sm:flex-row justify-between items-center mt-6 space-y-4 sm:space-y-0 bg-gray-50 p-4 rounded-lg">
          <!-- Información de paginación -->
          <div class="text-sm text-gray-600">
            <div>
              Mostrando {{ (paginacionClientes.currentPage - 1) * paginacionClientes.pageSize + 1 }} - 
              {{ Math.min(paginacionClientes.currentPage * paginacionClientes.pageSize, paginacionClientes.totalItems) }} 
              de {{ paginacionClientes.totalItems }} clientes
            </div>
            <div class="text-xs text-gray-500 mt-1">
              Página {{ paginacionClientes.currentPage }} de {{ paginacionClientes.totalPages }}
            </div>
          </div>

          <!-- Controles de paginación -->
          <div class="flex items-center space-x-2">
            <!-- Selector de tamaño de página -->
            <select 
              :value="paginacionClientes.pageSize"
              @change="cambiarTamanoPaginaClientes($event.target.value)"
              class="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-green-500"
            >
              <option value="10">10 por página</option>
              <option value="20">20 por página</option>
              <option value="50">50 por página</option>
            </select>

            <!-- Botones de navegación (solo si hay más de 1 página) -->
            <div v-if="paginacionClientes.totalPages > 1" class="flex space-x-1">
              <button 
                @click="paginaAnteriorClientes"
                :disabled="!paginacionClientes.hasPrevious"
                class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Anterior
              </button>

              <!-- Números de página -->
              <template v-for="page in getPaginasVisiblesClientes()" :key="page">
                <button 
                  v-if="page !== '...'"
                  @click="irAPaginaClientes(page)"
                  :class="[
                    'px-3 py-1 text-sm border rounded',
                    page === paginacionClientes.currentPage 
                      ? 'bg-green-600 text-white border-green-600' 
                      : 'border-gray-300 hover:bg-gray-50'
                  ]"
                >
                  {{ page }}
                </button>
                <span v-else class="px-2 py-1 text-sm text-gray-500">...</span>
              </template>

              <button 
                @click="paginaSiguienteClientes"
                :disabled="!paginacionClientes.hasNext"
                class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Siguiente
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    </div>

    <div v-show="activeStaffTab === 'productos'" class="staff-tab-panel staff-chart-grid">
    <!-- Gráfico: Productos Más Favoritos -->
    <section class="staff-panel">
      <h2 class="staff-section-title mb-4">Productos Más Favoritos</h2>
      <div v-if="mostFavoritedProducts.length > 0 && apexChartLoaded">
        <ApexChart
          type="bar"
          height="400"
          :options="favoritosChartOptions"
          :series="favoritosChartSeries"
        />
      </div>
      <div v-else-if="mostFavoritedProducts.length > 0 && !apexChartLoaded" class="text-center py-8">
        <div class="spinner-border text-red-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
      <p v-else class="text-gray-500 italic">No hay productos favoritos para mostrar.</p>
    </section>

    <!-- Gráfico: Palabras Más Buscadas -->
    <section class="staff-panel">
      <h2 class="staff-section-title mb-4">Palabras Más Buscadas</h2>
      <div v-if="mostSearchedWords.length > 0 && apexChartLoaded">
        <ApexChart
          type="bar"
          height="400"
          :options="busquedasChartOptions"
          :series="busquedasChartSeries"
        />
      </div>
      <div v-else-if="mostSearchedWords.length > 0 && !apexChartLoaded" class="text-center py-8">
        <div class="spinner-border text-red-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
      <p v-else class="text-gray-500 italic">No hay datos de búsquedas disponibles.</p>
    </section>

    <!-- Gráfico: Artículos Más Consultados -->
    <section class="staff-panel staff-panel-wide">
      <h2 class="staff-section-title mb-4">Top 10 Artículos Más Consultados</h2>
      <div v-if="articulosMasConsultados.length > 0 && apexChartLoaded">
        <ApexChart
          type="bar"
          height="450"
          :options="consultasChartOptions"
          :series="consultasChartSeries"
        />
        <div class="mt-4 text-sm text-gray-600">
          <p class="mb-2"><strong>📊 Resumen de Consultas:</strong></p>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div class="bg-blue-50 p-3 rounded">
              <span class="font-semibold">Total consultas:</span> 
              {{ articulosMasConsultados.reduce((sum, item) => sum + item.total_consultas, 0) }}
            </div>
            <div class="bg-green-50 p-3 rounded">
              <span class="font-semibold">Artículos únicos:</span> 
              {{ articulosMasConsultados.length }}
            </div>
            <div class="bg-yellow-50 p-3 rounded">
              <span class="font-semibold">Más consultado:</span> 
              {{ articulosMasConsultados[0]?.articulo_nombre || 'N/A' }}
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="articulosMasConsultados.length > 0 && !apexChartLoaded" class="text-center py-8">
        <div class="spinner-border text-blue-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
      <div v-else-if="loadingConsultas" class="text-center py-8">
        <div class="animate-spin inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full"></div>
        <p class="mt-2 text-gray-500">Cargando consultas de precios...</p>
      </div>
      <p v-else class="text-gray-500 italic">No hay datos de consultas de precios disponibles.</p>
    </section>

    </div>

    <div v-show="activeStaffTab === 'metricas'" class="staff-tab-panel staff-chart-grid">
    <!-- Gráfico: Evolución de Ventas -->
    <section class="staff-panel staff-panel-wide">
      <h2 class="staff-section-title mb-4">Evolución de Ventas (Últimos 30 Días)</h2>
      <div v-if="dailySalesData && dailySalesData.labels && dailySalesData.labels.length > 0 && apexChartLoaded">
        <ApexChart
          type="line"
          height="350"
          :options="ventasChartOptions"
          :series="ventasChartSeries"
        />
      </div>
      <div v-else-if="dailySalesData && dailySalesData.labels && dailySalesData.labels.length > 0 && !apexChartLoaded" class="text-center py-8">
        <div class="spinner-border text-red-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
      <p v-else class="text-gray-500 italic">No hay datos de ventas diarias disponibles.</p>
    </section>
    <!-- Gráfico: Sesiones por Hora -->
    <section class="staff-panel">
      <h2 class="staff-section-title mb-4">Sesiones por Hora</h2>
      <div v-if="sessionsByHour.labels.length > 0 && apexChartLoaded">
        <ApexChart
          type="area"
          height="300"
          :options="sessionsChartOptions"
          :series="sessionsChartSeries"
        />
      </div>
      <div v-else-if="sessionsByHour.labels.length > 0 && !apexChartLoaded" class="text-center py-8">
        <div class="spinner-border text-purple-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
      <p v-else class="text-gray-500 italic">No hay datos de sesiones horarias.</p>
    </section>

    <!-- Gráfico: Ingresos por Dispositivo -->
    <section class="staff-panel">
      <h2 class="staff-section-title mb-4">Ingresos por Dispositivo (User-Agent)</h2>
      <div v-if="(ingresosDispositivoSeries[0]?.data || []).length > 0 && apexChartLoaded">
        <ApexChart
          type="donut"
          height="320"
          :options="ingresosDispositivoChartOptions"
          :series="ingresosDispositivoSeries[0].data"
        />
        <p class="text-sm text-gray-600 mt-3">
          Total sesiones analizadas: <strong>{{ deviceIngress.total }}</strong>
        </p>
        <p class="text-xs text-gray-500 mt-1" v-if="deviceIngress.unknown > 0">
          No clasificados por user-agent: <strong>{{ deviceIngress.unknown }}</strong>
        </p>
      </div>
      <div v-else-if="apexChartLoaded" class="text-gray-500 italic">No hay ingresos para mostrar en el período.</div>
      <div v-else class="text-center py-8">
        <div class="spinner-border text-indigo-600" role="status">
          <span class="sr-only">Cargando gráfico...</span>
        </div>
      </div>
    </section>
    </div>
    </div>
  </div>

  <!-- Modal de Edición de Pedido -->
  <div v-if="mostrarModalEdicion" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
      <!-- Header del Modal -->
      <div class="p-6 border-b">
        <div class="flex justify-between items-center">
          <h3 class="text-xl font-semibold">Editar Pedido #{{ pedidoEditando?.id }}</h3>
          <button @click="cerrarModalEdicion" class="text-gray-500 hover:text-gray-700">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- Contenido del Modal -->
      <div class="p-6">
        <!-- Información básica del pedido -->
        <div class="mb-6">
          <h4 class="font-semibold mb-3 text-gray-800">Información del Pedido</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Estado</label>
              <select 
                v-model="formEdicion.estado"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="PENDIENTE">Pendiente</option>
                <option value="CONFIRMADO">Confirmado</option>
                <option value="EN_PROCESO">En Proceso</option>
                <option value="PREPARADO">Preparado</option>
                <option value="ENVIADO">Enviado</option>
                <option value="ENTREGADO">Entregado</option>
                <option value="CANCELADO">Cancelado</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input 
                v-model="formEdicion.email"
                type="email"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
                placeholder="Email del cliente"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
              <input 
                v-model="formEdicion.telefono"
                type="tel"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
                placeholder="Teléfono del cliente"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
              <input 
                v-model="formEdicion.direccion"
                type="text"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
                placeholder="Dirección de entrega"
              >
            </div>
          </div>
        </div>

        <!-- Notas adicionales -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-1">Notas del Pedido</label>
          <textarea 
            v-model="formEdicion.notas"
            rows="3"
            class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-red-500"
            placeholder="Notas adicionales sobre el pedido..."
          ></textarea>
        </div>

        <!-- Productos del pedido (solo lectura por ahora) -->
        <div class="mb-6">
          <h4 class="font-semibold mb-3 text-gray-800">Productos del Pedido</h4>
          <div class="border rounded-lg overflow-hidden">
            <table class="w-full">
              <thead class="bg-gray-50">
                <tr>
                  <th class="text-left py-3 px-4 font-medium text-gray-700">Producto</th>
                  <th class="text-center py-3 px-4 font-medium text-gray-700">Cantidad</th>
                  <th class="text-right py-3 px-4 font-medium text-gray-700">Precio Unit.</th>
                  <th class="text-right py-3 px-4 font-medium text-gray-700">Subtotal</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in pedidoEditando?.items || []" :key="item.id" class="border-t">
                  <td class="py-3 px-4">{{ getArticuloNombrePedido(item) }}</td>
                  <td class="py-3 px-4 text-center">{{ item.cantidad }}</td>
                  <td class="py-3 px-4 text-right">${{ formatCurrency(item.precio) }}</td>
                  <td class="py-3 px-4 text-right font-medium">${{ formatCurrency(item.cantidad * item.precio) }}</td>
                </tr>
              </tbody>
              <tfoot class="bg-gray-50 border-t">
                <tr>
                  <td colspan="3" class="py-3 px-4 text-right font-semibold">Total:</td>
                  <td class="py-3 px-4 text-right font-bold text-lg text-green-600">
                    ${{ formatCurrency(pedidoEditando?.total || 0) }}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>

      <!-- Footer del Modal -->
      <div class="p-6 border-t bg-gray-50 flex justify-end space-x-3">
        <button 
          @click="cerrarModalEdicion"
          class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
        >
          Cancelar
        </button>
        <button 
          @click="guardarEdicionPedido"
          :disabled="guardandoEdicion"
          class="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 transition"
        >
          {{ guardandoEdicion ? 'Guardando...' : 'Guardar Cambios' }}
        </button>
      </div>
    </div>
  </div>

  <!-- Modal de Nuevo Cliente -->
  <div v-if="mostrarModalNuevoCliente" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
    <div class="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
      <!-- Header del Modal -->
      <div class="p-6 border-b">
        <div class="flex justify-between items-center">
          <h3 class="text-xl font-semibold">Crear Nuevo Cliente</h3>
          <button @click="cerrarModalNuevoCliente" class="text-gray-500 hover:text-gray-700">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- Contenido del Modal -->
      <form @submit.prevent="guardarNuevoCliente" class="p-6">
        <!-- Datos de Usuario -->
        <div class="mb-6">
          <h4 class="font-semibold mb-3 text-gray-800">Datos de Usuario</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Nombre de Usuario <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.username"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="usuario123"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Email <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.email"
                type="email"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="usuario@email.com"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Contraseña <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.password"
                type="password"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Contraseña segura"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Estado</label>
              <select 
                v-model="formNuevoCliente.is_active"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option :value="true">Activo</option>
                <option :value="false">Inactivo</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Nombre <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.first_name"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Juan"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Apellido <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.last_name"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Pérez"
              >
            </div>
          </div>
        </div>

        <!-- Datos de Cliente -->
        <div class="mb-6">
          <h4 class="font-semibold mb-3 text-gray-800">Datos de Cliente</h4>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Número de Cliente <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.numero_cliente"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="CL001"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Nombre Comercial <span class="text-red-500">*</span></label>
              <input 
                v-model="formNuevoCliente.nombre"
                type="text"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="Nombre de la empresa"
              >
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Lista de Precio <span class="text-red-500">*</span></label>
              <select 
                v-model="formNuevoCliente.lista_precio"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option v-for="lista in datosAuxiliares.listas_precio" :key="lista.value" :value="lista.value">
                  {{ lista.label }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Localidad <span class="text-red-500">*</span></label>
              <select 
                v-model="formNuevoCliente.codigo_localidad"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option value="">Seleccionar localidad</option>
                <option v-for="localidad in datosAuxiliares.localidades" :key="localidad.codigo" :value="localidad.codigo">
                  {{ localidad.nombre }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Condición de Pago <span class="text-red-500">*</span></label>
              <select 
                v-model="formNuevoCliente.condicion_pago"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option value="">Seleccionar forma de pago</option>
                <option v-for="forma in datosAuxiliares.formas_pago" :key="forma.id" :value="forma.id">
                  {{ forma.nombre }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Tipo Responsable IVA <span class="text-red-500">*</span></label>
              <select 
                v-model="formNuevoCliente.tipo_responsable_iva"
                required
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option v-for="tipo in datosAuxiliares.tipos_responsable_iva" :key="tipo.value" :value="tipo.value">
                  {{ tipo.label }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">Régimen de Percepción</label>
              <select 
                v-model="formNuevoCliente.regimen_percepcion"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
              >
                <option v-for="regimen in datosAuxiliares.regimenes_percepcion" :key="regimen.value" :value="regimen.value">
                  {{ regimen.label }}
                </option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-gray-700 mb-1">CUIT</label>
              <input 
                v-model="formNuevoCliente.cuit"
                type="text"
                class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                placeholder="20-12345678-9"
              >
            </div>
          </div>
        </div>

        <!-- Dirección -->
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
          <textarea 
            v-model="formNuevoCliente.direccion"
            rows="2"
            class="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
            placeholder="Dirección completa del cliente"
          ></textarea>
        </div>

        <!-- Footer del Modal -->
        <div class="flex justify-end space-x-3 pt-6 border-t">
          <button 
            type="button"
            @click="cerrarModalNuevoCliente"
            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition"
          >
            Cancelar
          </button>
          <button 
            type="submit"
            :disabled="guardandoCliente"
            class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 transition"
          >
            {{ guardandoCliente ? 'Creando...' : 'Crear Cliente' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import api from '../services/api';
import { useAuthStore } from '../stores/auth';
import { dashboardStorage } from '../utils/storage';
import Toast from '../utils/toast';
// SweetAlert2 se importa dinámicamente cuando se necesita

export default {
  name: 'StaffDashboard',
  components: {
    // ApexChart se registra dinámicamente en mounted
  },
  data() {
    return {
      // Control de componentes dinámicos
      apexChartLoaded: false,
      
      // Datos principales
      mostFavoritedProducts: [],
      salesSummary: {},
      mostSearchedWords: [],
      dailySalesData: {
        labels: [],
        values: [],
      },
      sessionsByHour: {
        labels: [],
        data: [],
      },
      deviceIngress: {
        labels: ['Celular', 'Escritorio'],
        data: [0, 0],
        mobile: 0,
        desktop: 0,
        unknown: 0,
        total: 0,
      },
      // Nuevas métricas de sesiones
      sessionMetrics: {
        sessionsToday: 0,
        avgDuration: '0 min',
        activeUsers: 0,
        totalDuration: '0 h'
      },
      // Estado
      loading: false,
      lastUpdated: null,
      updateInterval: null,
      activeStaffTab: 'actividad',
      staffTabs: [
        {
          id: 'actividad',
          label: 'Actividad',
          description: 'Descargas y vistas'
        },
        {
          id: 'operacion',
          label: 'Operación',
          description: 'Pedidos y clientes'
        },
        {
          id: 'productos',
          label: 'Productos',
          description: 'Favoritos y búsquedas'
        },
        {
          id: 'metricas',
          label: 'Métricas',
          description: 'Ventas y sesiones'
        }
      ],
      
      // Gestión de Pedidos
      mostrarPedidos: false,
      loadingPedidos: false,
      todosPedidos: [],
      pedidosFiltrados: [],
      resumenPedidos: {
        pendientes: 0,
        confirmados: 0,
        en_proceso: 0,
        entregados: 0
      },
      filtroEstadoPedidos: '',
      filtroUsuario: '',
      filtroFechaDesde: '',
      enviandoEmail: false,
      
      // Filtro global por usuario
      filtroUsuarioGlobal: '',
      listaUsuarios: [],
      loadingUsuarios: false,
      mostrarSugerenciasUsuarios: false,
      usuariosBusqueda: '',
      busquedaTimeout: null,
      
      // Datos de consultas de precio
      articulosMasConsultados: [],
      loadingConsultas: false,
      
      // Paginación de Pedidos
      paginacionPedidos: {
        currentPage: 1,
        totalPages: 1,
        totalItems: 0,
        pageSize: 10,
        hasNext: false,
        hasPrevious: false
      },
      
      // Modal de Edición
      mostrarModalEdicion: false,
      pedidoEditando: null,
      formEdicion: {
        estado: '',
        email: '',
        telefono: '',
        direccion: '',
        notas: ''
      },
      guardandoEdicion: false,
      
      // Gestión de Clientes
      mostrarClientes: false,
      loadingClientes: false,
      todosClientes: [],
      clientesFiltrados: [],
      filtroNombreCliente: '',
      filtroNumeroCliente: '',
      filtroListaPrecio: '',
      
      // Paginación de Clientes
      paginacionClientes: {
        currentPage: 1,
        totalPages: 1,
        totalItems: 0,
        pageSize: 20,
        hasNext: false,
        hasPrevious: false
      },
      
      // Modal de Nuevo Cliente
      mostrarModalNuevoCliente: false,
      datosAuxiliares: {
        localidades: [],
        formas_pago: [],
        listas_precio: [],
        tipos_responsable_iva: [],
        regimenes_percepcion: []
      },
      formNuevoCliente: {
        username: '',
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        numero_cliente: '',
        nombre: '',
        lista_precio: '1',
        codigo_localidad: '',
        condicion_pago: '',
        tipo_responsable_iva: 'F',
        regimen_percepcion: '',
        cuit: '',
        direccion: '',
        is_active: true
      },
      guardandoCliente: false,
      // Resumen de exportaciones por cliente
      exportsSummary: [],
      loadingExportsSummary: false,
      // Export details modal
      showExportDetailsModal: false,
      exportDetails: [],
      exportDetailsPage: 1,
      exportDetailsPageSize: 10,
      exportDetailsTotalPages: 1,
      exportDetailsTotalItems: 0,
      loadingExportDetails: false,
      exportDetailsUsuarioFiltro: '',
      // Resumen de vistas de ofertas/discontinuados
      articulosVistasSummary: [],
      loadingArticulosVistasSummary: false,
    };
  },
  async created() {
    await this.fetchAllData();
  },
  computed: {
    favoritosChartSeries() {
      const data = Array.isArray(this.mostFavoritedProducts)
        ? this.mostFavoritedProducts.map(p => p.favoritos_count || 0)
        : [];
      return [{ name: 'Favoritos', data }];
    },
    favoritosChartOptions() {
      const labels = Array.isArray(this.mostFavoritedProducts)
        ? this.mostFavoritedProducts.map(p => p.nombre || 'Producto desconocido')
        : [];
      return {
        chart: { type: 'bar', foreColor: '#333' },
        plotOptions: { bar: { horizontal: true, barHeight: '80%' } },
        xaxis: { categories: labels, title: { text: 'Cantidad de Favoritos' } },
        yaxis: { labels: { maxWidth: 200 } },
        colors: ['#dc2626'],
        title: {
          text: 'Top 10 Productos Más Favoritos',
          align: 'center',
          style: { fontSize: '18px', color: '#b91c1c' },
        },
      };
    },
    busquedasChartSeries() {
      const data = Array.isArray(this.mostSearchedWords)
        ? this.mostSearchedWords.map(w => w.count || 0)
        : [];
      return [{ name: 'Búsquedas', data }];
    },
    busquedasChartOptions() {
      const labels = Array.isArray(this.mostSearchedWords)
        ? this.mostSearchedWords.map(w => w.query || 'Sin palabra')
        : [];
      return {
        chart: { type: 'bar', foreColor: '#333' },
        plotOptions: { bar: { horizontal: true } },
        xaxis: { categories: labels, title: { text: 'Número de Veces Buscada' } },
        colors: ['#0284c7'],
        title: {
          text: 'Top 10 Palabras Más Buscadas',
          align: 'center',
          style: { fontSize: '18px', color: '#0284c7' },
        },
      };
    },
    
    // Nuevas computed properties para consultas de precios
    consultasChartSeries() {
      const data = Array.isArray(this.articulosMasConsultados)
        ? this.articulosMasConsultados.map(item => item.total_consultas || 0)
        : [];
      return [{ name: 'Consultas', data }];
    },
    consultasChartOptions() {
      const labels = Array.isArray(this.articulosMasConsultados)
        ? this.articulosMasConsultados.map(item => {
            const nombre = item.articulo_nombre || 'Sin nombre';
            const clave = item.articulo_clave || '';
            // Truncar nombre si es muy largo
            const nombreCorto = nombre.length > 25 ? nombre.substring(0, 25) + '...' : nombre;
            return `${clave} - ${nombreCorto}`;
          })
        : [];
      return {
        chart: { 
          type: 'bar', 
          foreColor: '#333',
          height: 450
        },
        plotOptions: { 
          bar: { 
            horizontal: true,
            barHeight: '70%',
            dataLabels: {
              position: 'top'
            }
          } 
        },
        xaxis: { 
          categories: labels, 
          title: { text: 'Número de Consultas' },
          labels: {
            style: {
              fontSize: '11px'
            }
          }
        },
        yaxis: {
          labels: {
            style: {
              fontSize: '10px'
            },
            maxWidth: 200
          }
        },
        colors: ['#3b82f6'],
        title: {
          text: 'Top 10 Artículos Más Consultados',
          align: 'center',
          style: { fontSize: '18px', color: '#3b82f6' },
        },
        dataLabels: {
          enabled: true,
          style: {
            fontSize: '11px',
            fontWeight: 'bold',
            colors: ['#fff']
          }
        },
        tooltip: {
          y: {
            formatter: function(value) {
              return value + ' consultas';
            }
          }
        },
        grid: {
          show: true,
          strokeDashArray: 3
        }
      };
    },
    ventasChartSeries() {
        const values = this.dailySalesData?.values || [];
        return [{ name: 'Ventas ($)', data: values }];
      },
      ventasChartOptions() {
        const labels = this.dailySalesData?.labels || [];
        return {
          chart: { type: 'line', foreColor: '#333', zoom: { enabled: false } },
          xaxis: { 
            categories: labels, 
            title: { text: 'Fecha' }, 
            labels: { rotate: -45 } 
          },
           yaxis: { title: { text: 'Monto en $' } },
          stroke: { curve: 'smooth', width: 3 },
          markers: { size: 4 },
          colors: ['#16a34a'],
          title: {
            text: 'Ventas Diarias - Últimos 30 Días',
            align: 'center',
            style: { fontSize: '18px', color: '#16a34a' },
          },
        };
      },
    sessionsChartSeries() {
      const data = Array.isArray(this.sessionsByHour?.data) ? this.sessionsByHour.data : [];
      return [{ name: 'Sesiones', data }];
    },
    sessionsChartOptions() {
      const labels = Array.isArray(this.sessionsByHour?.labels) ? this.sessionsByHour.labels : [];
      return {
        chart: { type: 'area', foreColor: '#333', zoom: { enabled: false } },
        xaxis: { 
          categories: labels, 
          title: { text: 'Hora' }, 
        },
        yaxis: { title: { text: 'Nro. de Sesiones' } },
        stroke: { curve: 'smooth', width: 3 },
        markers: { size: 4 },
        colors: ['#8b5cf6'],
        title: {
          text: 'Sesiones por Hora - Promedio últimos 30 días',
          align: 'center',
          style: { fontSize: '18px', color: '#7c3aed' },
        },
        dataLabels: {
          enabled: false
        },
      };
    },
    ingresosDispositivoSeries() {
      const data = Array.isArray(this.deviceIngress?.data) ? this.deviceIngress.data : [0, 0];
      return [{ name: 'Ingresos', data }];
    },
    ingresosDispositivoChartOptions() {
      const labels = Array.isArray(this.deviceIngress?.labels)
        ? this.deviceIngress.labels
        : ['Celular', 'Escritorio'];
      return {
        chart: { type: 'donut', foreColor: '#333' },
        labels,
        colors: ['#0ea5e9', '#334155'],
        title: {
          text: 'Celular vs Escritorio (últimos 30 días)',
          align: 'center',
          style: { fontSize: '16px', color: '#4338ca' },
        },
        legend: {
          position: 'bottom',
        },
        dataLabels: {
          enabled: true,
          formatter: (value) => `${value.toFixed(1)}%`,
        },
      };
    },
  },
  methods: {
    // Helper para cargar SweetAlert2 dinámicamente
    async getSwal() {
      const { default: Swal } = await import('sweetalert2');
      return Swal;
    },

    async mostrarIngresosHoy() {
      try {
        console.log('📊 Cargando usuarios que ingresaron hoy...');
        
        // Obtener las sesiones de hoy (el backend usa su propia definición de "hoy")
        const response = await api.get('/api/staff/sessions/');
        
        console.log('📊 Respuesta del servidor:', response.data);
        const sesionesHoy = response.data;
        
        if (!sesionesHoy || sesionesHoy.length === 0) {
          const Swal = await this.getSwal();
          await Swal.fire({
            title: '📊 Ingresos de Hoy',
            html: '<p class="text-gray-500">No hay ingresos registrados hoy.</p>',
            icon: 'info',
            confirmButtonColor: '#7c3aed',
            confirmButtonText: 'Cerrar'
          });
          return;
        }
        
        // Agrupar por usuario y contar sus sesiones
        const usuariosMap = new Map();
        sesionesHoy.forEach(sesion => {
          const username = sesion.usuario__username;
          const clienteNombre = sesion.cliente__nombre || 'Sin cliente';
          const horaIngreso = new Date(sesion.inicio_sesion);
          
          if (!usuariosMap.has(username)) {
            usuariosMap.set(username, {
              username,
              clienteNombre,
              inicio_sesion: sesion.inicio_sesion,
              horaIngreso,
              totalIngresos: 1,
              sesiones: [sesion]
            });
          } else {
            const usuario = usuariosMap.get(username);
            usuario.totalIngresos++;
            usuario.sesiones.push(sesion);
            // Actualizar al ingreso más reciente
            if (horaIngreso > usuario.horaIngreso) {
              usuario.inicio_sesion = sesion.inicio_sesion;
              usuario.horaIngreso = horaIngreso;
            }
          }
        });
        
        // Convertir a array y ordenar por hora de último ingreso
        const usuarios = Array.from(usuariosMap.values())
          .sort((a, b) => b.horaIngreso - a.horaIngreso);
        
        console.log(`👥 Usuarios únicos: ${usuarios.length}`);
        
        // Generar HTML para el modal
        const usuariosHTML = usuarios.map((usuario, index) => `
          <div class="flex items-center justify-between p-3 ${index % 2 === 0 ? 'bg-gray-50' : 'bg-white'} rounded border-l-4 border-purple-500">
            <div class="flex-1">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-gray-800">${usuario.username}</span>
                ${usuario.totalIngresos > 1 ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800" title="${usuario.totalIngresos} sesiones hoy">${usuario.totalIngresos}x</span>` : ''}
              </div>
              <div class="text-sm text-gray-600">${usuario.clienteNombre}</div>
            </div>
            <div class="text-right">
              <div class="text-sm font-medium text-purple-600">
                ${usuario.horaIngreso.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div class="text-xs text-gray-500">
                ${usuario.totalIngresos > 1 ? 'Último ingreso' : usuario.horaIngreso.toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })}
              </div>
            </div>
          </div>
        `).join('');
        
        const Swal = await this.getSwal();
        await Swal.fire({
          title: `📊 Ingresos de Hoy`,
          html: `
            <div class="mb-4 grid grid-cols-2 gap-3">
              <div class="bg-purple-50 p-3 rounded-lg border border-purple-200">
                <div class="text-xs text-gray-600 uppercase mb-1">Usuarios Únicos</div>
                <div class="text-2xl font-bold text-purple-600">${usuarios.length}</div>
              </div>
              <div class="bg-blue-50 p-3 rounded-lg border border-blue-200">
                <div class="text-xs text-gray-600 uppercase mb-1">Total Sesiones</div>
                <div class="text-2xl font-bold text-blue-600">${sesionesHoy.length}</div>
              </div>
            </div>
            <div class="text-left max-h-96 overflow-y-auto space-y-2">
              ${usuariosHTML}
            </div>
            <div class="mt-4 text-xs text-gray-500 text-center border-t pt-3">
              💡 El badge muestra cuántas veces ingresó cada usuario hoy
            </div>
          `,
          icon: 'info',
          width: '650px',
          confirmButtonColor: '#7c3aed',
          confirmButtonText: 'Cerrar'
        });
        
      } catch (error) {
        console.error('❌ Error al cargar ingresos de hoy:', error);
        const Swal = await this.getSwal();
        await Swal.fire({
          title: 'Error',
          text: 'No se pudieron cargar los ingresos de hoy',
          icon: 'error',
          confirmButtonColor: '#dc2626'
        });
      }
    },

    async fetchAllData() {
      this.loading = true;
      try {
        // Solo usar caché si no hay filtro aplicado
        const cachedDashboard = !this.filtroUsuarioGlobal ? this.loadFromCache() : null;
        if (cachedDashboard) {
          Object.assign(this.$data, { ...this.$data, ...cachedDashboard });
          Toast.show('Datos cargados del caché', 'info', 2000);
          const cachedTime = localStorage.getItem('dashboard_cacheTime');
          if (cachedTime) {
            this.lastUpdated = this.formatLastUpdated(new Date(parseInt(cachedTime)));
          } else {
            this.updateLastUpdatedTime();
          }
          this.startUpdateTimer();
        } else {
          await this.fetchDashboardData();
          await this.fetchDailySales();
          await this.fetchArticulosMasConsultados();
          await this.fetchArticulosVistasSummary();
        }
      } catch (error) {
        console.error('Error al cargar datos del caché:', error);
        await this.fetchDashboardData();
        await this.fetchDailySales();
        await this.fetchArticulosMasConsultados();
        await this.fetchArticulosVistasSummary();
      } finally {
        this.loading = false;
      }
    },

    async reloadData() {
      this.loading = true;
      try {
        await this.fetchDashboardData(true);
        await this.fetchDailySales(true);
        await this.fetchArticulosMasConsultados();
        await this.fetchArticulosVistasSummary();
        await this.fetchArticulosVistasSummary();
        Toast.show('Datos recargados', 'success', 2000);
      } catch (error) {
        Toast.show('Error al recargar', 'error');
      } finally {
        this.loading = false;
      }
    },

    // Nueva función para cargar artículos más consultados
    async fetchArticulosMasConsultados() {
      this.loadingConsultas = true;
      try {
        const params = {};
        if (this.filtroUsuarioGlobal) {
          params.usuario = this.filtroUsuarioGlobal;
        }
        
        const response = await api.get('/api/staff/articulos-mas-consultados/', { params });
        this.articulosMasConsultados = response.data;
        console.log('📊 Artículos más consultados cargados:', this.articulosMasConsultados.length);
      } catch (error) {
        console.error('❌ Error al cargar artículos más consultados:', error);
        Toast.show('Error al cargar consultas de precios', 'error');
        this.articulosMasConsultados = [];
      } finally {
        this.loadingConsultas = false;
      }
    },

    // Nueva función para cargar resumen de exportaciones por usuario
    async fetchExportsSummary() {
      this.loadingExportsSummary = true;
      try {
        const params = {};
        if (this.filtroUsuarioGlobal) params.usuario = this.filtroUsuarioGlobal;
        const response = await api.get('/api/staff/exports-summary/', { params });
        // Normalizar fechas a objetos Date para mostrar
        this.exportsSummary = (response.data || []).map(item => ({
          ...item,
          last_export: item.last_export ? new Date(item.last_export) : null
        }));
        console.log('📥 Resumen de exportaciones cargado:', this.exportsSummary.length);
      } catch (error) {
        console.error('❌ Error al cargar resumen de exportaciones:', error);
        this.exportsSummary = [];
        Toast.show('Error al cargar resumen de exportaciones', 'error');
      } finally {
        this.loadingExportsSummary = false;
      }
    },

    // Resumen de vistas de ofertas/discontinuados
    async fetchArticulosVistasSummary() {
      this.loadingArticulosVistasSummary = true;
      try {
        const params = {};
        if (this.filtroUsuarioGlobal) params.usuario = this.filtroUsuarioGlobal;
        const response = await api.get('/api/staff/articulos-vistas/', { params });
        this.articulosVistasSummary = response.data || [];
        console.log('📊 Vistas de ofertas/discontinuados:', this.articulosVistasSummary.length);
      } catch (error) {
        console.error('❌ Error al cargar vistas de ofertas/discontinuados:', error);
        this.articulosVistasSummary = [];
        Toast.show('Error al cargar vistas de ofertas/discontinuados', 'error');
      } finally {
        this.loadingArticulosVistasSummary = false;
      }
    },

    // Abrir modal de detalles de exportaciones por usuario
    openExportDetails(item) {
      // item puede contener username o usuario_id
      this.exportDetailsUsuarioFiltro = item.username || item.usuario || '';
      this.exportDetailsPage = 1;
      this.showExportDetailsModal = true;
      this.fetchExportDetails(1);
    },

    closeExportDetails() {
      this.showExportDetailsModal = false;
      this.exportDetails = [];
      this.exportDetailsTotalPages = 1;
      this.exportDetailsTotalItems = 0;
    },

    // Obtener eventos de exportación (paginado) para un usuario
    async fetchExportDetails(page = 1) {
      if (!this.exportDetailsUsuarioFiltro) return;
      this.loadingExportDetails = true;
      try {
        const params = {
          usuario: this.exportDetailsUsuarioFiltro,
          page: page,
          page_size: this.exportDetailsPageSize
        };
        const response = await api.get('/api/staff/exports/', { params });
        // El endpoint devuelve paginación con keys: results + pagination
        this.exportDetails = response.data.results || [];
        const pag = response.data.pagination || {};
        this.exportDetailsPage = pag.current_page || page;
        this.exportDetailsTotalPages = pag.total_pages || 1;
        this.exportDetailsTotalItems = pag.total_items || (response.data.results ? response.data.results.length : 0);
      } catch (error) {
        console.error('❌ Error al cargar detalles de exportaciones:', error);
        Toast.show('Error al cargar detalles de exportaciones', 'error');
        this.exportDetails = [];
      } finally {
        this.loadingExportDetails = false;
      }
    },

    prettyParams(params) {
      try {
        if (!params) return '';
        if (typeof params === 'string') return params;
        return JSON.stringify(params, null, 2);
      } catch (e) {
        return String(params);
      }
    },

    formatDateTime(value) {
      if (!value) return '—';
      try {
        const d = new Date(value);
        return d.toLocaleString('es-AR');
      } catch (e) {
        return value;
      }
    },

    // Nueva función para cargar lista de usuarios
    async fetchUsuarios() {
      try {
        const response = await api.get('/api/staff/usuarios/');
        this.listaUsuarios = response.data;
        console.log('👥 Lista de usuarios cargada:', this.listaUsuarios.length);
      } catch (error) {
        console.error('❌ Error al cargar usuarios:', error);
        this.listaUsuarios = [];
      }
    },

    // Buscar usuarios de forma interactiva
    async buscarUsuarios(query) {
      if (!query || query.length < 2) {
        this.listaUsuarios = [];
        this.mostrarSugerenciasUsuarios = false;
        return;
      }

      this.loadingUsuarios = true;
      try {
        const response = await api.get('/api/staff/usuarios/', {
          params: {
            search: query,
            limit: 10
          }
        });
        
        this.listaUsuarios = response.data;
        this.mostrarSugerenciasUsuarios = this.listaUsuarios.length > 0;
        
        console.log(`🔍 Búsqueda usuarios "${query}": ${this.listaUsuarios.length} resultados`);
      } catch (error) {
        console.error('❌ Error al buscar usuarios:', error);
        this.listaUsuarios = [];
        this.mostrarSugerenciasUsuarios = false;
      } finally {
        this.loadingUsuarios = false;
      }
    },

    // Seleccionar usuario de las sugerencias
    seleccionarUsuario(usuario) {
      this.filtroUsuarioGlobal = usuario.username;
      this.usuariosBusqueda = `${usuario.username} - ${usuario.nombre_completo || usuario.first_name + ' ' + usuario.last_name}`;
      this.mostrarSugerenciasUsuarios = false;
      this.aplicarFiltroUsuarioGlobal();
    },

    // Limpiar filtro de usuario
    limpiarFiltroUsuario() {
      this.filtroUsuarioGlobal = '';
      this.usuariosBusqueda = '';
      this.mostrarSugerenciasUsuarios = false;
      this.aplicarFiltroUsuarioGlobal();
    },

    // Control de búsqueda con debounce
    onUsuarioBusquedaInput() {
      clearTimeout(this.busquedaTimeout);
      
      if (!this.usuariosBusqueda.trim()) {
        this.limpiarFiltroUsuario();
        return;
      }

      this.busquedaTimeout = setTimeout(() => {
        this.buscarUsuarios(this.usuariosBusqueda);
      }, 300);
    },

    // Aplicar filtro global por usuario
    async aplicarFiltroUsuarioGlobal() {
      this.loading = true;
      try {
        // Recargar todos los datos con el filtro aplicado
        await this.fetchDashboardData(true);
        await this.fetchDailySales(true);
        await this.fetchArticulosMasConsultados();
        
        // Si las secciones de gestión están abiertas, recargarlas también
        if (this.mostrarPedidos) {
          await this.cargarTodosPedidos(1);
        }
        
        if (this.mostrarClientes) {
          await this.cargarTodosClientes(1);
        }
        
        if (this.filtroUsuarioGlobal) {
          Toast.show(`Filtro aplicado para usuario: ${this.filtroUsuarioGlobal}`, 'info');
        } else {
          Toast.show('Filtro removido - mostrando todos los datos', 'info');
        }
      } catch (error) {
        Toast.show('Error al aplicar filtro', 'error');
      } finally {
        this.loading = false;
      }
    },

    loadFromCache() {
      const favoritos = dashboardStorage.get('mostFavoritedProducts');
      const summary = dashboardStorage.get('salesSummary');
      const busquedas = dashboardStorage.get('mostSearchedWords');
      const dailySales = dashboardStorage.get('dailySalesData');
      const sessionMetrics = dashboardStorage.get('sessionMetrics') || {
        sessionsToday: 0,
        avgDuration: '0 min',
        activeUsers: 0,
        totalDuration: '0 h'
      };
      const sessionsByHour = dashboardStorage.get('sessionsByHour') || { labels: [], data: [] };
      const deviceIngress = dashboardStorage.get('deviceIngress') || {
        labels: ['Celular', 'Escritorio'],
        data: [0, 0],
        mobile: 0,
        desktop: 0,
        unknown: 0,
        total: 0,
      };

      if (favoritos && summary && busquedas && dailySales) {
        return {
          mostFavoritedProducts: favoritos,
          salesSummary: summary,
          mostSearchedWords: busquedas,
          dailySalesData: dailySales,
          sessionMetrics,
          sessionsByHour,
          deviceIngress,
        };
      }
      return null;
    },

    async fetchDashboardData(force = false) {
      // No usar caché si hay filtro aplicado o si se fuerza la recarga
      if (!force && !this.filtroUsuarioGlobal) {
        const cached = dashboardStorage.get('mostFavoritedProducts');
        if (cached) {
          this.mostFavoritedProducts = cached;
          return;
        }
      }

      const loaderId = Toast.show('Cargando productos favoritos...', 'info', false);

      try {
        // Preparar parámetros de filtro
        const params = {};
        if (this.filtroUsuarioGlobal) {
          params.usuario = this.filtroUsuarioGlobal;
        }

        const [productsRes, salesRes, searchRes, metricsRes, deviceRes] = await Promise.all([
          api.get('/api/staff/most-favorited-products/', { params }),
          api.get('/api/staff/sales-summary/', { params }),
          api.get('/api/staff/most-searched-words/', { params }),
          api.get('/api/staff/session-metrics/', { params }), // Métricas de sesiones
          api.get('/api/staff/ingresos-dispositivo/', { params })
        ]);

        // Asignar datos
        this.mostFavoritedProducts = Array.isArray(productsRes.data) ? productsRes.data : [];
        this.salesSummary = salesRes.data || {};
        this.mostSearchedWords = Array.isArray(searchRes.data) ? searchRes.data : [];

        // Asignar métricas de sesión
        this.sessionMetrics = {
          sessionsToday: metricsRes.data.sessionsToday || 0,
          avgDuration: metricsRes.data.avgDuration || '0 min',
          activeUsers: metricsRes.data.activeUsers || 0,
          totalDuration: metricsRes.data.totalDuration || '0 h'
        };
        
        if (metricsRes.data.sessions_by_hour) {
            this.sessionsByHour = {
                labels: metricsRes.data.sessions_by_hour.labels || [],
                data: metricsRes.data.sessions_by_hour.data || [],
            };
        }

        this.deviceIngress = {
          labels: Array.isArray(deviceRes.data?.labels) ? deviceRes.data.labels : ['Celular', 'Escritorio'],
          data: Array.isArray(deviceRes.data?.data) ? deviceRes.data.data : [0, 0],
          mobile: deviceRes.data?.mobile || 0,
          desktop: deviceRes.data?.desktop || 0,
          unknown: deviceRes.data?.unknown || 0,
          total: deviceRes.data?.total || 0,
        };

        // Solo guardar en caché si no hay filtro aplicado
        if (!this.filtroUsuarioGlobal) {
          dashboardStorage.set('mostFavoritedProducts', this.mostFavoritedProducts);
          dashboardStorage.set('salesSummary', this.salesSummary);
          dashboardStorage.set('mostSearchedWords', this.mostSearchedWords);
          dashboardStorage.set('sessionMetrics', this.sessionMetrics);
          dashboardStorage.set('sessionsByHour', this.sessionsByHour);
          dashboardStorage.set('deviceIngress', this.deviceIngress);
          localStorage.setItem('dashboard_cacheTime', Date.now());
        }

  // Cargar resumen de exportaciones (no bloquear la carga principal)
  this.fetchExportsSummary();

        this.startUpdateTimer();

        Toast.remove(loaderId);
        Toast.show('Datos generales cargados', 'success', 2000);
      } catch (error) {
        Toast.remove(loaderId);
        Toast.show('Error al cargar métricas', 'error');

        // Asignar valores por defecto si falla
        this.sessionMetrics = {
          sessionsToday: 0,
          avgDuration: '0 min',
          activeUsers: 0,
          totalDuration: '0 h'
        };
        this.sessionsByHour = { labels: [], data: [] };
        this.deviceIngress = {
          labels: ['Celular', 'Escritorio'],
          data: [0, 0],
          mobile: 0,
          desktop: 0,
          unknown: 0,
          total: 0,
        };

        const authStore = useAuthStore();
        if (error.response?.status === 401 || error.response?.status === 403) {
          authStore.logout();
          this.$router.push('/login');
        }
      }
    },

    async fetchDailySales(force = false) {
      if (!force && !this.filtroUsuarioGlobal) {
        const cached = dashboardStorage.get('dailySalesData');
        if (cached && Array.isArray(cached.labels) && Array.isArray(cached.values)) {
          this.dailySalesData.labels = cached.labels;
          this.dailySalesData.values = cached.values;
          return;
        }
      }

      const loaderId = Toast.show('Cargando ventas diarias...', 'info', false);

      try {
        // Preparar parámetros de filtro
        const params = {};
        if (this.filtroUsuarioGlobal) {
          params.usuario = this.filtroUsuarioGlobal;
        }

        const response = await api.get('/api/staff/daily-sales/', { params });
        const data = response.data;

        const dates = Array.isArray(data.dates) ? data.dates : [];
        const sales = Array.isArray(data.sales) ? data.sales : [];

        this.dailySalesData.labels = dates;
        this.dailySalesData.values = sales;

        // Solo guardar en caché si no hay filtro aplicado
        if (!this.filtroUsuarioGlobal) {
          dashboardStorage.set('dailySalesData', { labels: dates, values: sales });
          localStorage.setItem('dashboard_cacheTime', Date.now());
        }

        Toast.remove(loaderId);
      } catch (error) {
        Toast.remove(loaderId);
        Toast.show('Error en ventas diarias', 'warning');
        this.dailySalesData.labels = [];
        this.dailySalesData.values = [];
      }
    },
    formatCurrency(value) {
      return parseFloat(value || 0).toFixed(2);
    },

    formatLastUpdated(date) {
      if (!date) return '';
      const now = new Date();
      const diffInMinutes = Math.floor((now - date) / 60000);

      if (diffInMinutes < 1) return 'justo ahora';
      if (diffInMinutes < 60) return `hace ${diffInMinutes} min`;
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${hours}:${minutes}`;
    },

    startUpdateTimer() {
      this.updateLastUpdatedTime();
      if (this.updateInterval) clearInterval(this.updateInterval);
      this.updateInterval = setInterval(() => {
        this.updateLastUpdatedTime();
      }, 60000); // Cada minuto
    },

    updateLastUpdatedTime() {
      const now = new Date();
      this.lastUpdated = this.formatLastUpdated(now);
    },

    // === MÉTODOS PARA GESTIÓN DE PEDIDOS ===
    
    togglePedidosView() {
      this.mostrarPedidos = !this.mostrarPedidos;
      if (this.mostrarPedidos && this.todosPedidos.length === 0) {
        this.cargarTodosPedidos();
      }
    },

    async cargarTodosPedidos(page = 1) {
      this.loadingPedidos = true;
      try {
        console.log('🔄 Cargando pedidos página', page, 'para staff...');
        
        // Construir parámetros de query
        const params = new URLSearchParams({
          page: page.toString(),
          page_size: this.paginacionPedidos.pageSize.toString()
        });
        
        // Agregar filtros si están activos
        if (this.filtroEstadoPedidos) {
          params.append('estado', this.filtroEstadoPedidos);
        }
        
        // Priorizar filtro global por usuario si existe, sino usar filtro local
        const usuarioFiltro = this.filtroUsuarioGlobal || this.filtroUsuario;
        if (usuarioFiltro) {
          params.append('usuario', usuarioFiltro);
        }
        
        if (this.filtroFechaDesde) {
          params.append('fecha_desde', this.filtroFechaDesde);
        }
        
        // Endpoint especial para staff que devuelve todos los pedidos con paginación
        const url = `/api/staff/pedidos/?${params.toString()}`;
        console.log('🌐 URL de request:', url);
        
        if (this.filtroUsuarioGlobal) {
          console.log('🔍 Aplicando filtro global de usuario a pedidos:', this.filtroUsuarioGlobal);
        }
        
        const response = await api.get(url);
        
        // Actualizar datos con la respuesta paginada
        this.todosPedidos = response.data.results || [];
        
        // Mapear correctamente los datos de paginación del backend
        const paginationData = response.data.pagination || {};
        this.paginacionPedidos = {
          currentPage: paginationData.current_page || 1,
          totalPages: paginationData.total_pages || 1,
          totalItems: paginationData.total_items || 0,
          pageSize: paginationData.page_size || 10,
          hasNext: paginationData.has_next || false,
          hasPrevious: paginationData.has_previous || false
        };
        
        // Debug para verificar paginación
        console.log('📊 Datos de paginación recibidos:', response.data.pagination);
        console.log('📊 Datos de paginación mapeados:', this.paginacionPedidos);
        console.log('📊 Total pages:', this.paginacionPedidos.totalPages);
        console.log('📊 Current page:', this.paginacionPedidos.currentPage);
        
        // Usar directamente los pedidos ya que vienen filtrados del backend
        this.pedidosFiltrados = this.todosPedidos;
        
        // Calcular resumen
        this.calcularResumenPedidos();
        
        console.log('✅ Pedidos cargados:', this.todosPedidos.length, 'de', this.paginacionPedidos.totalItems);
        
        if (page === 1) {
          Toast.show(`${this.paginacionPedidos.totalItems} pedidos encontrados`, 'success', 2000);
        }
        
      } catch (error) {
        console.error('❌ Error al cargar pedidos:', error);
        Toast.show('Error al cargar pedidos', 'error');
        
        // Verificar autenticación
        if (error.response?.status === 401 || error.response?.status === 403) {
          const authStore = useAuthStore();
          authStore.logout();
          this.$router.push('/login');
        }
      } finally {
        this.loadingPedidos = false;
      }
    },

    calcularResumenPedidos() {
      const resumen = {
        pendientes: 0,
        confirmados: 0,
        en_proceso: 0,
        entregados: 0
      };
      
      this.todosPedidos.forEach(pedido => {
        switch (pedido.estado) {
          case 'PENDIENTE':
            resumen.pendientes++;
            break;
          case 'CONFIRMADO':
            resumen.confirmados++;
            break;
          case 'EN_PROCESO':
            resumen.en_proceso++;
            break;
          case 'ENTREGADO':
            resumen.entregados++;
            break;
        }
      });
      
      this.resumenPedidos = resumen;
    },

    aplicarFiltrosPedidos() {
      // Con paginación en el backend, simplemente recargamos desde la página 1
      console.log('🔍 Aplicando filtros, reseteando a página 1...');
      this.paginacionPedidos.currentPage = 1;
      this.cargarTodosPedidos(1);
    },

    async cambiarEstadoPedido(pedidoId, nuevoEstado) {
      try {
        console.log(`🔄 Cambiando estado del pedido ${pedidoId} a ${nuevoEstado}`);
        
        const response = await api.patch(`/api/staff/pedidos/${pedidoId}/`, {
          estado: nuevoEstado
        });
        
        // Actualizar en la lista local
        const pedido = this.todosPedidos.find(p => p.id === pedidoId);
        if (pedido) {
          pedido.estado = nuevoEstado;
        }
        
        // Recalcular resumen y filtros
        this.calcularResumenPedidos();
        this.aplicarFiltrosPedidos();
        
        Toast.show(`Estado cambiado a ${nuevoEstado}`, 'success', 2000);
        
      } catch (error) {
        console.error('❌ Error al cambiar estado:', error);
        Toast.show('Error al cambiar estado del pedido', 'error');
        
        // Recargar para revertir cambio visual
        this.cargarTodosPedidos();
      }
    },

    async reenviarConfirmacion(pedidoId) {
      if (this.enviandoEmail) return;
      
      this.enviandoEmail = true;
      try {
        console.log(`📧 Reenviando confirmación del pedido ${pedidoId}`);
        
        await api.post(`/api/staff/pedidos/${pedidoId}/reenviar-email/`);
        
        Toast.show('Email de confirmación reenviado', 'success', 3000);
        
      } catch (error) {
        console.error('❌ Error al reenviar email:', error);
        Toast.show('Error al reenviar email de confirmación', 'error');
      } finally {
        this.enviandoEmail = false;
      }
    },

    verDetallePedidoStaff(pedido) {
      // Mostrar modal con detalle completo del pedido
      console.log('📋 Detalle completo del pedido:', pedido);
      
      // Crear contenido del modal con información detallada
      const modalContent = this.crearContenidoDetallePedido(pedido);
      
      // Crear modal dinámico
      const modal = document.createElement('div');
      modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
      modal.innerHTML = modalContent;
      
      // Agregar event listeners
      modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('close-modal')) {
          document.body.removeChild(modal);
        }
      });
      
      document.body.appendChild(modal);
    },

    crearContenidoDetallePedido(pedido) {
      const productosHtml = (pedido.items || []).map(item => `
        <tr class="border-b">
          <td class="py-2">${this.getArticuloNombrePedido(item)}</td>
          <td class="py-2 text-center">${item.cantidad}</td>
          <td class="py-2 text-right">$${this.formatCurrency(item.precio)}</td>
          <td class="py-2 text-right">$${this.formatCurrency(item.cantidad * item.precio)}</td>
        </tr>
      `).join('');

      return `
        <div class="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
          <div class="p-6 border-b">
            <div class="flex justify-between items-center">
              <h3 class="text-xl font-semibold">Detalle del Pedido #${pedido.id}</h3>
              <button class="close-modal text-gray-500 hover:text-gray-700">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
              </button>
            </div>
          </div>
          
          <div class="p-6">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div>
                <h4 class="font-semibold mb-2">Información del Cliente</h4>
                <p><strong>Usuario:</strong> ${pedido.usuario_nombre || pedido.user}</p>
                <p><strong>Email:</strong> ${pedido.email || 'No disponible'}</p>
                <p><strong>Teléfono:</strong> ${pedido.telefono || 'No disponible'}</p>
              </div>
              <div>
                <h4 class="font-semibold mb-2">Información del Pedido</h4>
                <p><strong>Estado:</strong> <span class="${this.getEstadoClasses(pedido.estado)}">${this.getEstadoTexto(pedido.estado)}</span></p>
                <p><strong>Fecha:</strong> ${this.formatDate(pedido.fecha_creacion)}</p>
                <p><strong>Total:</strong> <span class="text-lg font-semibold text-green-600">$${this.formatCurrency(pedido.total)}</span></p>
              </div>
            </div>
            
            <div class="mb-6">
              <h4 class="font-semibold mb-3">Productos del Pedido</h4>
              <table class="w-full">
                <thead class="bg-gray-50">
                  <tr>
                    <th class="text-left py-2 px-3">Producto</th>
                    <th class="text-center py-2 px-3">Cantidad</th>
                    <th class="text-right py-2 px-3">Precio Unit.</th>
                    <th class="text-right py-2 px-3">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  ${productosHtml}
                </tbody>
              </table>
            </div>
            
            <div class="flex justify-end space-x-3">
              <button class="close-modal px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600">
                Cerrar
              </button>
            </div>
          </div>
        </div>
      `;
    },

    editarPedido(pedido) {
      console.log('✏️ Abriendo modal de edición para pedido:', pedido);
      
      // Configurar el pedido para edición
      this.pedidoEditando = { ...pedido };
      
      // Inicializar el formulario con los datos actuales
      this.formEdicion = {
        estado: pedido.estado || '',
        email: pedido.email || '',
        telefono: pedido.telefono || '',
        direccion: pedido.direccion || '',
        notas: pedido.notas || ''
      };
      
      // Mostrar el modal
      this.mostrarModalEdicion = true;
    },

    cerrarModalEdicion() {
      this.mostrarModalEdicion = false;
      this.pedidoEditando = null;
      this.formEdicion = {
        estado: '',
        email: '',
        telefono: '',
        direccion: '',
        notas: ''
      };
      this.guardandoEdicion = false;
    },

    async guardarEdicionPedido() {
      if (!this.pedidoEditando) return;
      
      this.guardandoEdicion = true;
      try {
        console.log('💾 Guardando cambios del pedido', this.pedidoEditando.id);
        
        // Preparar datos para enviar
        const datosActualizacion = {
          estado: this.formEdicion.estado,
          email: this.formEdicion.email,
          telefono: this.formEdicion.telefono,
          direccion: this.formEdicion.direccion,
          notas: this.formEdicion.notas
        };
        
        // Enviar actualización al backend
        const response = await api.patch(`/api/staff/pedidos/${this.pedidoEditando.id}/`, datosActualizacion);
        
        // Actualizar el pedido localmente
        const index = this.todosPedidos.findIndex(p => p.id === this.pedidoEditando.id);
        if (index !== -1) {
          // Mantener los datos originales y actualizar solo los campos editados
          this.todosPedidos[index] = { ...this.todosPedidos[index], ...datosActualizacion };
        }
        
        // Recalcular resumen si cambió el estado
        this.calcularResumenPedidos();
        
        Toast.show('Pedido actualizado correctamente', 'success', 3000);
        this.cerrarModalEdicion();
        
      } catch (error) {
        console.error('❌ Error al guardar cambios del pedido:', error);
        Toast.show('Error al guardar cambios del pedido', 'error');
      } finally {
        this.guardandoEdicion = false;
      }
    },

    async cancelarPedidoStaff(pedidoId) {
      if (!confirm('¿Estás seguro de que quieres cancelar este pedido?')) {
        return;
      }
      
      await this.cambiarEstadoPedido(pedidoId, 'CANCELADO');
    },

    // === MÉTODOS DE PAGINACIÓN ===
    
    irAPagina(page) {
      if (page >= 1 && page <= this.paginacionPedidos.totalPages) {
        this.paginacionPedidos.currentPage = page;
        this.cargarTodosPedidos(page);
      }
    },

    paginaAnterior() {
      if (this.paginacionPedidos.hasPrevious) {
        this.irAPagina(this.paginacionPedidos.currentPage - 1);
      }
    },

    paginaSiguiente() {
      if (this.paginacionPedidos.hasNext) {
        this.irAPagina(this.paginacionPedidos.currentPage + 1);
      }
    },

    cambiarTamanoPagina(nuevoTamano) {
      console.log('📏 Cambiando tamaño de página a:', nuevoTamano);
      this.paginacionPedidos.pageSize = parseInt(nuevoTamano);
      this.paginacionPedidos.currentPage = 1;
      this.cargarTodosPedidos(1);
    },

    getPaginasVisibles() {
      const totalPages = this.paginacionPedidos.totalPages;
      const currentPage = this.paginacionPedidos.currentPage;
      const pages = [];

      if (totalPages <= 7) {
        // Si hay 7 páginas o menos, mostrar todas
        for (let i = 1; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        // Lógica para mostrar páginas con elipsis
        if (currentPage <= 4) {
          // Mostrar 1,2,3,4,5...N
          for (let i = 1; i <= 5; i++) {
            pages.push(i);
          }
          pages.push('...');
          pages.push(totalPages);
        } else if (currentPage >= totalPages - 3) {
          // Mostrar 1...N-4,N-3,N-2,N-1,N
          pages.push(1);
          pages.push('...');
          for (let i = totalPages - 4; i <= totalPages; i++) {
            pages.push(i);
          }
        } else {
          // Mostrar 1...current-1,current,current+1...N
          pages.push(1);
          pages.push('...');
          for (let i = currentPage - 1; i <= currentPage + 1; i++) {
            pages.push(i);
          }
          pages.push('...');
          pages.push(totalPages);
        }
      }

      return pages;
    },

    getEstadoSelectClasses(estado) {
      const baseClasses = 'focus:outline-none focus:ring-2 focus:ring-offset-2';
      
      switch (estado) {
        case 'PENDIENTE':
          return `${baseClasses} bg-yellow-100 text-yellow-800 focus:ring-yellow-500`;
        case 'CONFIRMADO':
          return `${baseClasses} bg-blue-100 text-blue-800 focus:ring-blue-500`;
        case 'EN_PROCESO':
          return `${baseClasses} bg-purple-100 text-purple-800 focus:ring-purple-500`;
        case 'PREPARADO':
          return `${baseClasses} bg-indigo-100 text-indigo-800 focus:ring-indigo-500`;
        case 'ENVIADO':
          return `${baseClasses} bg-orange-100 text-orange-800 focus:ring-orange-500`;
        case 'ENTREGADO':
          return `${baseClasses} bg-green-100 text-green-800 focus:ring-green-500`;
        case 'CANCELADO':
          return `${baseClasses} bg-red-100 text-red-800 focus:ring-red-500`;
        default:
          return `${baseClasses} bg-gray-100 text-gray-800 focus:ring-gray-500`;
      }
    },

    getTotalCantidadPedido(items) {
      if (!items || !Array.isArray(items)) return 0;
      return items.reduce((total, item) => total + (item.cantidad || 0), 0);
    },

    getArticuloNombrePedido(item) {
      return item.articulo_detalle?.nombre || item.articulo?.nombre || 'Producto sin nombre';
    },

    formatDate(dateString) {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    },

    // === MÉTODOS PARA GESTIÓN DE CLIENTES ===
    
    toggleClientesView() {
      this.mostrarClientes = !this.mostrarClientes;
      if (this.mostrarClientes && this.todosClientes.length === 0) {
        this.cargarTodosClientes();
      }
    },

    async cargarTodosClientes(page = 1) {
      this.loadingClientes = true;
      try {
        console.log('🔄 Cargando clientes página', page, 'para staff...');
        
        // Construir parámetros de query
        const params = new URLSearchParams({
          page: page.toString(),
          page_size: this.paginacionClientes.pageSize.toString()
        });
        
        // Agregar filtros si están activos
        if (this.filtroNombreCliente) {
          params.append('nombre', this.filtroNombreCliente);
        }
        if (this.filtroNumeroCliente) {
          params.append('numero_cliente', this.filtroNumeroCliente);
        }
        if (this.filtroListaPrecio) {
          params.append('lista_precio', this.filtroListaPrecio);
        }
        
        // Agregar filtro global por usuario si está activo
        if (this.filtroUsuarioGlobal) {
          params.append('usuario', this.filtroUsuarioGlobal);
        }
        
        const url = `/api/staff/clientes/?${params.toString()}`;
        console.log('🌐 URL de request clientes:', url);
        
        if (this.filtroUsuarioGlobal) {
          console.log('🔍 Aplicando filtro global de usuario a clientes:', this.filtroUsuarioGlobal);
        }
        
        const response = await api.get(url);
        
        // Mapear correctamente los datos de paginación del backend
        const paginationData = response.data.pagination || {};
        this.paginacionClientes = {
          currentPage: paginationData.current_page || 1,
          totalPages: paginationData.total_pages || 1,
          totalItems: paginationData.total_items || 0,
          pageSize: paginationData.page_size || 20,
          hasNext: paginationData.has_next || false,
          hasPrevious: paginationData.has_previous || false
        };
        
        // Actualizar datos
        this.todosClientes = response.data.results || [];
        this.clientesFiltrados = this.todosClientes;
        
        console.log('✅ Clientes cargados:', this.todosClientes.length, 'de', this.paginacionClientes.totalItems);
        
        if (page === 1) {
          Toast.show(`${this.paginacionClientes.totalItems} clientes encontrados`, 'success', 2000);
        }
        
      } catch (error) {
        console.error('❌ Error al cargar clientes:', error);
        Toast.show('Error al cargar clientes', 'error');
        
        if (error.response?.status === 401 || error.response?.status === 403) {
          const authStore = useAuthStore();
          authStore.logout();
          this.$router.push('/login');
        }
      } finally {
        this.loadingClientes = false;
      }
    },

    aplicarFiltrosClientes() {
      console.log('🔍 Aplicando filtros de clientes, reseteando a página 1...');
      this.paginacionClientes.currentPage = 1;
      this.cargarTodosClientes(1);
    },

    // Métodos de paginación para clientes
    irAPaginaClientes(page) {
      if (page >= 1 && page <= this.paginacionClientes.totalPages) {
        this.paginacionClientes.currentPage = page;
        this.cargarTodosClientes(page);
      }
    },

    paginaAnteriorClientes() {
      if (this.paginacionClientes.hasPrevious) {
        this.irAPaginaClientes(this.paginacionClientes.currentPage - 1);
      }
    },

    paginaSiguienteClientes() {
      if (this.paginacionClientes.hasNext) {
        this.irAPaginaClientes(this.paginacionClientes.currentPage + 1);
      }
    },

    cambiarTamanoPaginaClientes(nuevoTamano) {
      console.log('📏 Cambiando tamaño de página de clientes a:', nuevoTamano);
      this.paginacionClientes.pageSize = parseInt(nuevoTamano);
      this.paginacionClientes.currentPage = 1;
      this.cargarTodosClientes(1);
    },

    getPaginasVisiblesClientes() {
      const totalPages = this.paginacionClientes.totalPages;
      const currentPage = this.paginacionClientes.currentPage;
      const pages = [];

      if (totalPages <= 7) {
        for (let i = 1; i <= totalPages; i++) {
          pages.push(i);
        }
      } else {
        if (currentPage <= 4) {
          for (let i = 1; i <= 5; i++) {
            pages.push(i);
          }
          pages.push('...');
          pages.push(totalPages);
        } else if (currentPage >= totalPages - 3) {
          pages.push(1);
          pages.push('...');
          for (let i = totalPages - 4; i <= totalPages; i++) {
            pages.push(i);
          }
        } else {
          pages.push(1);
          pages.push('...');
          for (let i = currentPage - 1; i <= currentPage + 1; i++) {
            pages.push(i);
          }
          pages.push('...');
          pages.push(totalPages);
        }
      }

      return pages;
    },

    // Acciones sobre clientes
    async verDetalleCliente(cliente) {
      try {
        console.log('👤 Cargando detalle de cliente:', cliente.id);
        
        const response = await api.get(`/api/staff/clientes/${cliente.id}/`);
        const clienteDetalle = response.data;
        
        // Cargar SweetAlert dinámicamente y mostrar modal
        const Swal = await this.getSwal();
        await Swal.fire({
          title: `Cliente: ${clienteDetalle.numero_cliente}`,
          html: `
            <div class="text-left space-y-3">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <strong>Datos de Usuario:</strong><br>
                  <span class="text-gray-600">Usuario:</span> ${clienteDetalle.username}<br>
                  <span class="text-gray-600">Nombre:</span> ${clienteDetalle.first_name} ${clienteDetalle.last_name}<br>
                  <span class="text-gray-600">Email:</span> ${clienteDetalle.email}<br>
                  <span class="text-gray-600">Estado:</span> <span class="${clienteDetalle.is_active ? 'text-green-600' : 'text-red-600'}">${clienteDetalle.is_active ? 'Activo' : 'Inactivo'}</span>
                </div>
                <div>
                  <strong>Datos Comerciales:</strong><br>
                  <span class="text-gray-600">Razón Social:</span> ${clienteDetalle.nombre}<br>
                  <span class="text-gray-600">Lista de Precio:</span> Lista ${clienteDetalle.lista_precio}<br>
                  <span class="text-gray-600">Tipo IVA:</span> ${clienteDetalle.tipo_responsable_iva_display}<br>
                  <span class="text-gray-600">CUIT:</span> ${clienteDetalle.cuit || 'N/A'}
                </div>
              </div>
              <div>
                <strong>Ubicación y Contacto:</strong><br>
                <span class="text-gray-600">Localidad:</span> ${clienteDetalle.localidad?.nombre || 'N/A'}<br>
                <span class="text-gray-600">Forma de Pago:</span> ${clienteDetalle.condicion_pago?.nombre || 'N/A'}<br>
                <span class="text-gray-600">Dirección:</span> ${clienteDetalle.direccion || 'No especificada'}
              </div>
              
              ${clienteDetalle.bonificaciones && clienteDetalle.bonificaciones.length > 0 ? `
                <div class="bg-blue-50 border border-blue-200 rounded p-3">
                  <strong class="text-blue-800">📊 Bonificaciones Activas:</strong>
                  <div class="mt-2 space-y-2">
                    ${clienteDetalle.bonificaciones.map(bonif => `
                      <div class="flex items-center justify-between bg-white p-2 rounded border border-blue-100">
                        <span class="text-sm">
                          <span class="font-medium">Rango:</span> ${bonif.desde_articulo} → ${bonif.hasta_articulo}
                        </span>
                        <span class="text-lg font-bold text-green-600">${bonif.bonificacion}%</span>
                      </div>
                    `).join('')}
                  </div>
                </div>
              ` : ''}
              
              <div class="text-sm text-gray-500 border-t pt-2">
                <span class="text-gray-600">Registro:</span> ${this.formatDate(clienteDetalle.date_joined)}<br>
                <span class="text-gray-600">Último acceso:</span> ${clienteDetalle.last_login ? this.formatDate(clienteDetalle.last_login) : 'Nunca'}
              </div>
            </div>
          `,
          icon: 'info',
          confirmButtonText: 'Cerrar',
          confirmButtonColor: '#059669',
          width: '600px'
        });
        
      } catch (error) {
        console.error('❌ Error al cargar detalle del cliente:', error);
        Swal.fire({
          title: 'Error',
          text: 'No se pudo cargar el detalle del cliente',
          icon: 'error',
          confirmButtonColor: '#dc2626'
        });
      }
    },

    async editarCliente(cliente) {
      try {
        console.log('✏️ Cargando datos para editar cliente:', cliente.id);
        
        // Cargar datos completos del cliente
        const [clienteResponse, auxiliaresResponse] = await Promise.all([
          api.get(`/api/staff/clientes/${cliente.id}/`),
          api.get('/api/staff/clientes/datos-auxiliares/')
        ]);
        
        const clienteDetalle = clienteResponse.data;
        const auxiliares = auxiliaresResponse.data;
        
        // Crear opciones para los selects
        const localidadesOptions = auxiliares.localidades.map(loc => 
          `<option value="${loc.codigo}" ${loc.codigo === clienteDetalle.localidad?.codigo ? 'selected' : ''}>${loc.nombre}</option>`
        ).join('');
        
        const formasPagoOptions = auxiliares.formas_pago.map(forma => 
          `<option value="${forma.id}" ${forma.id === clienteDetalle.condicion_pago?.id ? 'selected' : ''}>${forma.nombre}</option>`
        ).join('');
        
        const tiposIvaOptions = auxiliares.tipos_responsable_iva.map(tipo => 
          `<option value="${tipo.value}" ${tipo.value === clienteDetalle.tipo_responsable_iva ? 'selected' : ''}>${tipo.label}</option>`
        ).join('');
        
        const listasOptions = auxiliares.listas_precio.map(lista => 
          `<option value="${lista.value}" ${lista.value === clienteDetalle.lista_precio ? 'selected' : ''}>${lista.label}</option>`
        ).join('');
        
        const regimenesOptions = auxiliares.regimenes_percepcion.map(regimen => 
          `<option value="${regimen.value}" ${regimen.value === clienteDetalle.regimen_percepcion ? 'selected' : ''}>${regimen.label}</option>`
        ).join('');
        
        const Swal = await this.getSwal();
        const { value: formData, isConfirmed } = await Swal.fire({
          title: `Editar Cliente: ${clienteDetalle.numero_cliente}`,
          html: `
            <div class="space-y-4 text-left">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Email:</label>
                  <input id="email" type="email" value="${clienteDetalle.email}" class="w-full p-2 border rounded">
                </div>
                <div>
                  <label class="block text-sm font-medium mb-1">Estado:</label>
                  <select id="is_active" class="w-full p-2 border rounded">
                    <option value="true" ${clienteDetalle.is_active ? 'selected' : ''}>Activo</option>
                    <option value="false" ${!clienteDetalle.is_active ? 'selected' : ''}>Inactivo</option>
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Nombre:</label>
                  <input id="first_name" type="text" value="${clienteDetalle.first_name}" class="w-full p-2 border rounded">
                </div>
                <div>
                  <label class="block text-sm font-medium mb-1">Apellido:</label>
                  <input id="last_name" type="text" value="${clienteDetalle.last_name}" class="w-full p-2 border rounded">
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Razón Social:</label>
                  <input id="nombre" type="text" value="${clienteDetalle.nombre}" class="w-full p-2 border rounded">
                </div>
                <div>
                  <label class="block text-sm font-medium mb-1">Lista de Precio:</label>
                  <select id="lista_precio" class="w-full p-2 border rounded">
                    ${listasOptions}
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Localidad:</label>
                  <select id="codigo_localidad" class="w-full p-2 border rounded">
                    ${localidadesOptions}
                  </select>
                </div>
                <div>
                  <label class="block text-sm font-medium mb-1">Forma de Pago:</label>
                  <select id="condicion_pago" class="w-full p-2 border rounded">
                    ${formasPagoOptions}
                  </select>
                </div>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-sm font-medium mb-1">Tipo IVA:</label>
                  <select id="tipo_responsable_iva" class="w-full p-2 border rounded">
                    ${tiposIvaOptions}
                  </select>
                </div>
                <div>
                  <label class="block text-sm font-medium mb-1">CUIT:</label>
                  <input id="cuit" type="text" value="${clienteDetalle.cuit || ''}" class="w-full p-2 border rounded">
                </div>
              </div>
              <div>
                <label class="block text-sm font-medium mb-1">Dirección:</label>
                <textarea id="direccion" class="w-full p-2 border rounded" rows="2">${clienteDetalle.direccion || ''}</textarea>
              </div>
              
              <label class="flex items-center gap-2 text-sm font-medium">
                <input id="puede_descargar_lista" type="checkbox" ${clienteDetalle.puede_descargar_lista ? 'checked' : ''}>
                Puede descargar lista de artículos
              </label>
              <!-- Sección de Bonificaciones -->
              ${clienteDetalle.bonificaciones && clienteDetalle.bonificaciones.length > 0 ? `
                <div class="mt-4 p-4 bg-blue-50 border border-blue-200 rounded">
                  <h3 class="text-lg font-semibold mb-3 text-blue-800">📊 Bonificaciones Activas</h3>
                  <div class="space-y-2">
                    ${clienteDetalle.bonificaciones.map(bonif => `
                      <div class="flex items-center justify-between bg-white p-3 rounded border border-blue-100">
                        <div class="flex-1">
                          <span class="font-medium text-gray-700">Rango:</span>
                          <span class="text-gray-900 ml-2">${bonif.desde_articulo} → ${bonif.hasta_articulo}</span>
                        </div>
                        <div class="text-right">
                          <span class="text-2xl font-bold text-green-600">${bonif.bonificacion}%</span>
                          <span class="text-xs text-gray-500 block">descuento</span>
                        </div>
                      </div>
                    `).join('')}
                  </div>
                </div>
              ` : ''}
              
              <div>
                <label class="block text-sm font-medium mb-1">Nueva Contraseña (opcional):</label>
                <input id="password" type="password" placeholder="Dejar vacío para no cambiar" class="w-full p-2 border rounded">
              </div>
            </div>
          `,
          focusConfirm: false,
          showCancelButton: true,
          confirmButtonText: 'Guardar Cambios',
          cancelButtonText: 'Cancelar',
          confirmButtonColor: '#059669',
          cancelButtonColor: '#6b7280',
          width: '700px',
          preConfirm: () => {
            return {
              email: document.getElementById('email').value,
              is_active: document.getElementById('is_active').value === 'true',
              puede_descargar_lista: document.getElementById('puede_descargar_lista').checked,
              first_name: document.getElementById('first_name').value,
              last_name: document.getElementById('last_name').value,
              nombre: document.getElementById('nombre').value,
              lista_precio: document.getElementById('lista_precio').value,
              codigo_localidad: document.getElementById('codigo_localidad').value,
              condicion_pago: document.getElementById('condicion_pago').value,
              tipo_responsable_iva: document.getElementById('tipo_responsable_iva').value,
              cuit: document.getElementById('cuit').value,
              direccion: document.getElementById('direccion').value,
              password: document.getElementById('password').value || undefined
            };
          }
        });
        
        if (isConfirmed && formData) {
          // Mostrar loading
          Swal.fire({
            title: 'Guardando cambios...',
            allowOutsideClick: false,
            didOpen: () => {
              Swal.showLoading();
            }
          });
          
          try {
            await api.put(`/api/staff/clientes/${cliente.id}/`, formData);
            
            Swal.fire({
              title: '¡Éxito!',
              text: 'Cliente actualizado correctamente',
              icon: 'success',
              confirmButtonColor: '#059669'
            });
            
            // Recargar lista de clientes
            this.cargarTodosClientes(this.paginacionClientes.currentPage);
            
          } catch (error) {
            console.error('❌ Error al actualizar cliente:', error);
            const errorMsg = error.response?.data?.error || 'Error al actualizar cliente';
            Swal.fire({
              title: 'Error',
              text: errorMsg,
              icon: 'error',
              confirmButtonColor: '#dc2626'
            });
          }
        }
        
      } catch (error) {
        console.error('❌ Error al cargar datos para edición:', error);
        const Swal = await this.getSwal();
        Swal.fire({
          title: 'Error',
          text: 'No se pudieron cargar los datos para edición',
          icon: 'error',
          confirmButtonColor: '#dc2626'
        });
      }
    },

    async toggleActivoCliente(cliente) {
      const accion = cliente.is_active ? 'desactivar' : 'activar';
      const icon = cliente.is_active ? 'warning' : 'question';
      const color = cliente.is_active ? '#f59e0b' : '#059669';
      
      const Swal = await this.getSwal();
      const result = await Swal.fire({
        title: `¿${accion.charAt(0).toUpperCase() + accion.slice(1)} cliente?`,
        text: `¿Estás seguro de que quieres ${accion} a ${cliente.nombre}?`,
        icon: icon,
        showCancelButton: true,
        confirmButtonColor: color,
        cancelButtonColor: '#6b7280',
        confirmButtonText: `Sí, ${accion}`,
        cancelButtonText: 'Cancelar'
      });

      if (result.isConfirmed) {
        try {
          console.log(`🔄 ${accion} cliente:`, cliente.numero_cliente);
          
          await api.put(`/api/staff/clientes/${cliente.id}/`, {
            is_active: !cliente.is_active
          });
          
          Swal.fire({
            title: '¡Éxito!',
            text: `Cliente ${cliente.is_active ? 'desactivado' : 'activado'} correctamente`,
            icon: 'success',
            confirmButtonColor: '#059669',
            timer: 2000,
            showConfirmButton: false
          });
          
          // Actualizar localmente
          cliente.is_active = !cliente.is_active;
          
        } catch (error) {
          console.error(`❌ Error al ${accion} cliente:`, error);
          Swal.fire({
            title: 'Error',
            text: `Error al ${accion} cliente`,
            icon: 'error',
            confirmButtonColor: '#dc2626'
          });
        }
      }
    },

    async eliminarCliente(cliente) {
      const Swal = await this.getSwal();
      const result = await Swal.fire({
        title: '¿Eliminar cliente?',
        html: `¿Estás seguro de que quieres eliminar a <strong>${cliente.nombre}</strong>?<br><br>
               <small class="text-gray-500">Esta acción desactivará permanentemente el cliente.</small>`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc2626',
        cancelButtonColor: '#6b7280',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
      });

      if (result.isConfirmed) {
        try {
          console.log('🗑️ Eliminando cliente:', cliente.numero_cliente);
          
          await api.delete(`/api/staff/clientes/${cliente.id}/`);
          
          Swal.fire({
            title: '¡Eliminado!',
            text: 'Cliente eliminado correctamente',
            icon: 'success',
            confirmButtonColor: '#059669',
            timer: 2000,
            showConfirmButton: false
          });
          
          // Recargar lista de clientes
          this.cargarTodosClientes(this.paginacionClientes.currentPage);
          
        } catch (error) {
          console.error('❌ Error al eliminar cliente:', error);
          Swal.fire({
            title: 'Error',
            text: 'Error al eliminar cliente',
            icon: 'error',
            confirmButtonColor: '#dc2626'
          });
        }
      }
    },

    // Modal de nuevo cliente
    async abrirModalNuevoCliente() {
      try {
        // Cargar datos auxiliares si no los tenemos
        if (this.datosAuxiliares.localidades.length === 0) {
          const response = await api.get('/api/staff/clientes/datos-auxiliares/');
          this.datosAuxiliares = response.data;
        }
        
        this.mostrarModalNuevoCliente = true;
      } catch (error) {
        console.error('❌ Error al cargar datos auxiliares:', error);
        Toast.show('Error al cargar datos del formulario', 'error');
      }
    },

    cerrarModalNuevoCliente() {
      this.mostrarModalNuevoCliente = false;
      this.formNuevoCliente = {
        username: '',
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        numero_cliente: '',
        nombre: '',
        lista_precio: '1',
        codigo_localidad: '',
        condicion_pago: '',
        tipo_responsable_iva: 'F',
        regimen_percepcion: '',
        cuit: '',
        direccion: '',
        is_active: true
      };
      this.guardandoCliente = false;
    },

    async guardarNuevoCliente() {
      this.guardandoCliente = true;
      try {
        console.log('💾 Guardando nuevo cliente:', this.formNuevoCliente);
        
        const response = await api.post('/api/staff/clientes/', this.formNuevoCliente);
        
        Toast.show(response.data.message || 'Cliente creado exitosamente', 'success', 3000);
        this.cerrarModalNuevoCliente();
        
        // Recargar lista de clientes
        this.cargarTodosClientes(1);
        
      } catch (error) {
        console.error('❌ Error al crear cliente:', error);
        const errorMsg = error.response?.data?.error || 'Error al crear cliente';
        Toast.show(errorMsg, 'error');
      } finally {
        this.guardandoCliente = false;
      }
    },

    // Métodos auxiliares
    formatCurrency(value) {
      if (!value || isNaN(value)) return '0.00';
      const number = parseFloat(value);
      return new Intl.NumberFormat('es-AR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(number);
    },

    formatDate(dateString) {
      if (!dateString) return 'N/A';
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('es-AR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).format(date);
    },

    aplicarFiltroClientes() {
      if (!this.filtroClientes.trim()) {
        this.clientesFiltrados = [...this.todosClientes];
      } else {
        const filtro = this.filtroClientes.toLowerCase();
        this.clientesFiltrados = this.todosClientes.filter(cliente => 
          cliente.numero_cliente.toLowerCase().includes(filtro) ||
          cliente.nombre.toLowerCase().includes(filtro) ||
          cliente.username.toLowerCase().includes(filtro) ||
          cliente.email.toLowerCase().includes(filtro) ||
          (cliente.cuit && cliente.cuit.includes(filtro))
        );
      }
      
      // Reiniciar paginación al filtrar
      this.paginacionClientes.currentPage = 1;
      console.log(`🔍 Filtro aplicado: ${this.clientesFiltrados.length} clientes encontrados`);
    },

    limpiarFiltroClientes() {
      this.filtroClientes = '';
      this.aplicarFiltroClientes();
    },

    // Manejar clicks fuera del componente de búsqueda
    handleClickOutside(event) {
      const searchContainer = event.target.closest('.relative');
      if (!searchContainer) {
        this.mostrarSugerenciasUsuarios = false;
      }
    },
  },
  beforeUnmount() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }
    if (this.busquedaTimeout) {
      clearTimeout(this.busquedaTimeout);
    }
    // Remover event listener para clicks fuera del componente
    document.removeEventListener('click', this.handleClickOutside);
  },
  async mounted() {
    // Cargar ApexChart dinámicamente
    try {
      const ApexChartModule = await import('vue3-apexcharts');
      this.$options.components.ApexChart = ApexChartModule.default;
      this.apexChartLoaded = true;
    } catch (error) {
      console.error('Error al cargar ApexChart:', error);
    }
    
    // Agregar event listener para cerrar sugerencias al hacer click fuera
    document.addEventListener('click', this.handleClickOutside);
  },
};
</script>

<style scoped>
  .animate-spin {
    animation: spin 1s linear infinite;
  }
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .last-updated {
    font-size: 0.75rem;
    color: #6b7280;
    background: #f3f4f6;
    padding: 0.5rem 0.75rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    display: inline-block;
  }
  .staff-metric-card {
    min-height: 112px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    padding: 1rem;
    text-align: center;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    transition: border-color 150ms ease, box-shadow 150ms ease;
  }
  .staff-metric-card h3 {
    font-size: 0.8rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0;
  }
  .staff-metric-card p {
    margin-top: 0.55rem;
    font-size: 1.7rem;
    line-height: 2rem;
    font-weight: 800;
  }
  .staff-tabs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    padding: 0.5rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  }
  .staff-tab {
    border-radius: 8px;
    padding: 0.75rem;
    text-align: left;
    color: #475569;
    transition: background 150ms ease, color 150ms ease, box-shadow 150ms ease;
  }
  .staff-tab span {
    display: block;
    font-size: 0.95rem;
    font-weight: 800;
  }
  .staff-tab small {
    display: block;
    margin-top: 0.15rem;
    font-size: 0.75rem;
    color: #64748b;
  }
  .staff-tab:hover {
    background: #f8fafc;
  }
  .staff-tab-active {
    background: #b91c1c;
    color: #fff;
    box-shadow: 0 8px 18px rgba(185, 28, 28, 0.16);
  }
  .staff-tab-active small {
    color: #fee2e2;
  }
  .staff-tab-panel {
    display: grid;
    gap: 1rem;
  }
  .staff-chart-grid {
    grid-template-columns: minmax(0, 1fr);
  }
  .staff-panel {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #fff;
    padding: 1rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  }
  .staff-section-title {
    font-size: 1.1rem;
    line-height: 1.5rem;
    font-weight: 800;
    color: #111827;
  }
  @media (min-width: 768px) {
    .staff-tabs {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .staff-panel {
      padding: 1.25rem;
    }
  }
  @media (min-width: 1180px) {
    .staff-chart-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .staff-panel-wide {
      grid-column: span 2 / span 2;
    }
  }
</style>
