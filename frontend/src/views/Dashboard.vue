<template>
  <div class="ui-page space-y-6">
    <PageHeader
      :title="`Hola, ${fullName}`"
      description="Resumen de cuenta y accesos rápidos para armar pedidos, revisar comprobantes y repetir compras."
    >
      <template #actions>
        <ActionButton to="/productos">
          Comprar productos
        </ActionButton>
        <ActionButton to="/pedidos" variant="secondary">
          Mis pedidos
        </ActionButton>
        <ActionButton v-if="puedeDescargarLista" type="button" variant="secondary" class="!border-green-600 !bg-green-600 !text-white hover:!bg-green-700" @click="exportLista">
          <span v-if="downloading">Preparando...</span>
          <span v-else class="inline-flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Descargar lista
          </span>
        </ActionButton>
      </template>
    </PageHeader>

    <!-- Alerta de Facturas Vencidas/Por Vencer -->
    <transition name="slide-fade">
      <div v-if="!kpisLoading && !kpisError && (kpis.deuda_vencida > 0 || kpis.deuda_por_vencer > 0)" class="space-y-3">
        <!-- Alerta de Deuda Vencida (Crítica) -->
        <div 
          v-if="kpis.deuda_vencida > 0"
          class="bg-gradient-to-r from-red-500 to-red-600 rounded-xl shadow-lg p-4 sm:p-5 border-l-4 border-red-700 animate-pulse-subtle"
        >
          <div class="flex items-center justify-between flex-wrap gap-3">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-white/20 rounded-full">
                <svg class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <p class="text-white font-bold text-lg">¡Tenés facturas vencidas!</p>
                <p class="text-red-100 text-sm">
                  Total adeudado: <span class="font-bold text-white">${{ formatCurrency(kpis.deuda_vencida) }}</span>
                </p>
              </div>
            </div>
            <router-link 
              to="/comprobantes"
              class="inline-flex items-center px-4 py-2 bg-white text-red-600 text-sm font-semibold rounded-lg hover:bg-red-50 transition-all shadow-md hover:shadow-lg gap-2"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
              </svg>
              Ver Detalle
            </router-link>
          </div>
        </div>

        <!-- Alerta de Deuda por Vencer (Advertencia) -->
        <div 
          v-if="kpis.deuda_por_vencer > 0 && kpis.deuda_vencida === 0"
          class="bg-gradient-to-r from-amber-400 to-orange-400 rounded-xl shadow-lg p-4 sm:p-5 border-l-4 border-amber-600"
        >
          <div class="flex items-center justify-between flex-wrap gap-3">
            <div class="flex items-center gap-3">
              <div class="p-2 bg-white/20 rounded-full">
                <svg class="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <p class="text-white font-bold text-lg">Facturas próximas a vencer</p>
                <p class="text-amber-100 text-sm">
                  Total por vencer: <span class="font-bold text-white">${{ formatCurrency(kpis.deuda_por_vencer) }}</span>
                </p>
              </div>
            </div>
            <router-link 
              to="/comprobantes"
              class="inline-flex items-center px-4 py-2 bg-white text-amber-600 text-sm font-semibold rounded-lg hover:bg-amber-50 transition-all shadow-md hover:shadow-lg gap-2"
            >
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
              </svg>
              Ver Comprobantes
            </router-link>
          </div>
        </div>

        <!-- Mini alerta si hay deuda por vencer ADEMÁS de vencida -->
        <div 
          v-if="kpis.deuda_por_vencer > 0 && kpis.deuda_vencida > 0"
          class="bg-gradient-to-r from-amber-100 to-orange-100 rounded-lg p-3 border border-amber-300 flex items-center justify-between flex-wrap gap-2"
        >
          <div class="flex items-center gap-2">
            <svg class="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-amber-800 text-sm">
              También tenés <span class="font-bold">${{ formatCurrency(kpis.deuda_por_vencer) }}</span> por vencer próximamente
            </p>
          </div>
        </div>
      </div>
    </transition>

    <!-- Acceso rápido: Descargar lista -->
    <div v-if="puedeDescargarLista" class="rounded-2xl border border-green-200 bg-gradient-to-r from-green-50 to-emerald-50 p-5 sm:p-6 shadow-sm flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div class="flex items-start gap-3">
        <div class="p-2.5 bg-green-600 rounded-xl text-white shadow-sm">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        </div>
        <div>
          <h3 class="text-base font-black text-green-900">Descargar lista de artículos</h3>
          <p class="text-sm text-green-800/80">Bajá tu lista personalizada en Excel con precios según tu condición comercial (favoritos).</p>
        </div>
      </div>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="inline-flex items-center gap-2 rounded-lg bg-green-600 px-5 py-2.5 text-sm font-bold text-white shadow hover:bg-green-700 disabled:opacity-60" :disabled="downloading" @click="exportLista">
          <svg v-if="!downloading" xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span v-if="downloading" class="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
          {{ downloading ? 'Preparando...' : 'Descargar Excel' }}
        </button>
        <RouterLink to="/productos" class="inline-flex items-center justify-center rounded-lg border border-green-600 bg-white px-5 py-2.5 text-sm font-bold text-green-700 hover:bg-green-50">Ver catálogo</RouterLink>
      </div>
    </div>

    <!-- Información del Usuario -->
    <div class="bg-white backdrop-blur-sm rounded-2xl shadow-lg border border-gray-300 p-6 sm:p-8 transition-all hover:shadow-xl w-full">
      <h2 class="text-2xl sm:text-3xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <span class="text-red-600">👋</span>
        Bienvenido, {{ fullName }}
      </h2>

      <div class="space-y-4 text-gray-600">
        <div class="flex items-center gap-3">
          <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
          <strong class="text-gray-900 min-w-[80px]">Nombre:</strong>
          <span>{{ fullName }}</span>
        </div>
        
        <div class="flex items-center gap-3">
          <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
          </svg>
          <strong class="text-gray-900 min-w-[80px]">Usuario:</strong>
          <span class="font-mono text-sm bg-gray-50 px-2 py-0.5 rounded">{{ authStore.user?.username }}</span>
        </div>
        
        <div class="flex items-center gap-3">
          <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <strong class="text-gray-900 min-w-[80px]">Email:</strong>
          <span class="font-medium">{{ authStore.user?.email }}</span>
        </div>
        
        <div class="flex items-center gap-3">
          <svg class="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <strong class="text-gray-900 min-w-[80px]">Rol:</strong>
          <span
            :class="[
              'px-2 py-1 rounded-full text-xs font-semibold',
              authStore.user?.is_staff ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'
            ]"
          >
            {{ authStore.user?.is_staff ? 'Administrador' : 'Usuario' }}
          </span>
        </div>
      </div>

      <!-- Línea decorativa -->
      <div class="mt-6 pt-4 border-t border-gray-300">
        <p class="text-sm text-gray-500 text-center">
          Último acceso: <span class="font-medium text-gray-600">{{ lastLogin }}</span>
        </p>
      </div>
    </div>

    <!-- KPIs Dashboard -->
    <div class="bg-white backdrop-blur-sm rounded-2xl shadow-lg border border-gray-300 p-6 sm:p-8 transition-all hover:shadow-xl w-full">
      <h3 class="text-xl sm:text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        Resumen de Cuenta
      </h3>

      <!-- Loading State -->
      <div v-if="kpisLoading" class="flex items-center justify-center py-12">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-red-600"></div>
        <span class="ml-3 text-gray-500">Cargando información...</span>
      </div>

      <!-- Error State -->
      <div v-else-if="kpisError" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
        <div class="flex items-center">
          <svg class="h-5 w-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p class="ml-2 text-red-800">Error al cargar la información financiera</p>
        </div>
      </div>

      <!-- KPIs Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <!-- Saldo Total -->
        <div class="bg-gradient-to-r from-red-50 to-red-100 rounded-lg p-6 border border-red-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-red-600 text-sm font-medium">Saldo Total</p>
              <p class="text-2xl font-bold text-red-900">${{ formatCurrency(kpis.saldo_total) }}</p>
            </div>
            <div class="p-3 bg-red-200 rounded-full">
              <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Cantidad de Comprobantes -->
        <div class="bg-gradient-to-r from-blue-50 to-blue-100 rounded-lg p-6 border border-blue-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-blue-600 text-sm font-medium">Comprobantes</p>
              <p class="text-2xl font-bold text-blue-900">{{ kpis.cantidad_comprobantes }}</p>
            </div>
            <div class="p-3 bg-blue-200 rounded-full">
              <svg class="h-6 w-6 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Total de Pagos -->
        <div class="bg-gradient-to-r from-green-50 to-green-100 rounded-lg p-6 border border-green-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-green-600 text-sm font-medium">Total Pagos</p>
              <p class="text-2xl font-bold text-green-900">${{ formatCurrency(kpis.total_pagos) }}</p>
            </div>
            <div class="p-3 bg-green-200 rounded-full">
              <svg class="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Total de Créditos -->
        <div class="bg-gradient-to-r from-purple-50 to-purple-100 rounded-lg p-6 border border-purple-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-purple-600 text-sm font-medium">Total Créditos</p>
              <p class="text-2xl font-bold text-purple-900">${{ formatCurrency(kpis.total_creditos) }}</p>
            </div>
            <div class="p-3 bg-purple-200 rounded-full">
              <svg class="h-6 w-6 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Total Facturas y Débitos -->
        <div class="bg-gradient-to-r from-orange-50 to-orange-100 rounded-lg p-6 border border-orange-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-orange-600 text-sm font-medium">Facturas y Débitos</p>
              <p class="text-2xl font-bold text-orange-900">${{ formatCurrency(kpis.total_facturas_debitos) }}</p>
            </div>
            <div class="p-3 bg-orange-200 rounded-full">
              <svg class="h-6 w-6 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 14l6-6m-5.5.5h.01m4.99 5h.01M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16l3.5-2 3.5 2 3.5-2 3.5 2zM10 8.5a.5.5 0 11-1 0 .5.5 0 011 0zm5 5a.5.5 0 11-1 0 .5.5 0 011 0z" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Deuda Vencida -->
        <div class="bg-gradient-to-r from-red-50 to-red-100 rounded-lg p-6 border border-red-200">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-red-600 text-sm font-medium">Deuda Vencida</p>
              <p class="text-2xl font-bold text-red-900">${{ formatCurrency(kpis.deuda_vencida) }}</p>
            </div>
            <div class="p-3 bg-red-200 rounded-full">
              <svg class="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      <!-- Resumen de Deuda -->
      <div v-if="!kpisLoading && !kpisError" class="mt-6 p-4 bg-gray-50 rounded-lg">
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <h4 class="font-semibold text-gray-900">Resumen de Deuda</h4>
          <router-link 
            to="/comprobantes"
            class="inline-flex items-center px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 transition-colors gap-2"
          >
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Ver Comprobantes
          </router-link>
        </div>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span class="text-gray-600">Deuda por vencer:</span>
            <span class="font-medium text-gray-900">${{ formatCurrency(kpis.deuda_por_vencer) }}</span>
          </div>
          <div>
            <span class="text-gray-600">Deuda vencida:</span>
            <span class="font-medium text-red-600">${{ formatCurrency(kpis.deuda_vencida) }}</span>
          </div>
        </div>
      </div>
    </div>
    <!-- Grafico Compras vs Pagos -->
    <div>
      <ComprasPagosChart />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getDashboardKpis } from '../services/dashboard'
import ComprasPagosChart from '../components/ComprasPagosChart.vue'
import ActionButton from '@/components/ui/ActionButton.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import api from '@/services/api'
import { usePermisoDescarga } from '@/services/permisoDescarga'

const puedeDescargarLista = usePermisoDescarga()
import * as XLSX from 'xlsx'

const authStore = useAuthStore()
const router = useRouter()

// Estados para KPIs
const kpis = ref({
  saldo_total: 0,
  cantidad_comprobantes: 0,
  total_pagos: 0,
  total_creditos: 0,
  total_facturas_debitos: 0,
  deuda_vencida: 0,
  deuda_por_vencer: 0
})
const kpisLoading = ref(false)
const kpisError = ref(false)
const downloading = ref(false)

const notify = (msg, type = 'info') => {
  if (window.Toast?.show) window.Toast.show(msg, type, 4000)
  else if (type === 'error') console.error(msg)
  else console.log(msg)
}

const exportLista = async () => {
  if (downloading.value) return
  downloading.value = true
  try {
    notify('Preparando exportación de favoritos...', 'info')
    const modalidad = localStorage.getItem('articulos_modalidad') || 'retira'
    const conImpuestos = (localStorage.getItem('articulos_con_impuestos') ?? 'true') === 'true'
    const condicionPago = localStorage.getItem('condicion_pago') || ''
    const params = { modalidad, con_impuestos: conImpuestos }
    if (condicionPago) params.condicion_pago = condicionPago
    const response = await api.get('/api/exportar-favoritos/', { params })
    if (response.data?.success) {
      const { data, total_articulos, parametros } = response.data
      if (!data || data.length === 0) {
        notify('No tenés artículos favoritos para exportar. Marcá productos como favoritos en el catálogo.', 'info')
        return
      }
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
      const fecha = new Date().toISOString().split('T')[0]
      const fileName = `favoritos_${parametros.modalidad}_${parametros.con_impuestos ? 'con' : 'sin'}_impuestos_${fecha}.xlsx`
            const fileData = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
      const fileBlob = new Blob([fileData], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      })
      const fileUrl = URL.createObjectURL(fileBlob)
      const downloadLink = document.createElement('a')
      downloadLink.href = fileUrl
      downloadLink.download = fileName
      document.body.appendChild(downloadLink)
      downloadLink.click()
      downloadLink.remove()
      window.setTimeout(() => URL.revokeObjectURL(fileUrl), 1000)
      notify(`✅ ${total_articulos} artículos exportados correctamente.`, 'success')
    } else {
      notify('Error al preparar la exportación.', 'error')
    }
  } catch (error) {
    console.error('Error en exportación:', error)
    const msg = error.response?.data?.error || 'Error al exportar favoritos. Intentá nuevamente.'
    notify(msg, 'error')
  } finally {
    downloading.value = false
  }
}

// Nombre completo
const fullName = computed(() => {
  const { first_name, last_name } = authStore.user || {}
  if (first_name && last_name) return `${first_name} ${last_name}`
  return first_name || last_name || authStore.user?.username || 'Sin nombre'
})

// Último login (ejemplo estático, puedes reemplazarlo con el real)
const lastLogin = computed(() => {
  return new Date().toLocaleString('es-ES', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
})

// Función para formatear moneda
const formatCurrency = (value) => {
  if (!value) return '0.00'
  return new Intl.NumberFormat('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

// Función para cargar KPIs
const loadKpis = async () => {
  kpisLoading.value = true
  kpisError.value = false
  
  try {
    const response = await getDashboardKpis()
    if (response.success) {
      kpis.value = response.data
      console.log('✅ KPIs cargados exitosamente:', response.data)
    } else {
      kpisError.value = true
      console.error('❌ Error en respuesta KPIs:', response)
      // Mostrar toast de error si está disponible
      if (window.Toast) {
        window.Toast.show('Error al cargar la información financiera', 'error', 5000)
      }
    }
  } catch (error) {
    kpisError.value = true
    console.error('❌ Error al cargar KPIs:', error)
    // Mostrar toast de error si está disponible
    if (window.Toast) {
      const errorMsg = error.response?.data?.message || error.message || 'Error de conexión'
      window.Toast.show(`Error: ${errorMsg}`, 'error', 5000)
    }
  } finally {
    kpisLoading.value = false
  }
}

// Cargar KPIs al montar el componente
onMounted(() => {
  if (window.innerWidth < 768 && !authStore.user?.is_staff) {
    router.replace('/productos')
    return
  }

  loadKpis()
})
</script>

<style scoped>
/* Animación de pulso sutil para alertas críticas */
.animate-pulse-subtle {
  animation: pulse-subtle 2s ease-in-out infinite;
}

@keyframes pulse-subtle {
  0%, 100% {
    box-shadow: 0 10px 15px -3px rgba(239, 68, 68, 0.3), 0 4px 6px -2px rgba(239, 68, 68, 0.2);
  }
  50% {
    box-shadow: 0 20px 25px -5px rgba(239, 68, 68, 0.4), 0 10px 10px -5px rgba(239, 68, 68, 0.3);
  }
}

/* Transición de entrada/salida */
.slide-fade-enter-active {
  transition: all 0.4s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.3s ease-in;
}

.slide-fade-enter-from {
  transform: translateY(-20px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}
</style>
