<template>
  <div class="ui-page space-y-6 pb-10">
    <PageHeader
      title="Revisar y enviar pedido"
      description="Confirmá productos y condiciones antes de enviar la solicitud a Ventas FASA."
    >
      <template #actions>
        <ActionButton to="/carrito" variant="secondary">Volver a editar</ActionButton>
      </template>
    </PageHeader>

    <EmptyState
      v-if="cart.items.length === 0"
      title="No hay productos para revisar"
      description="Volvé al catálogo y agregá productos al carrito."
    >
      <template #actions><ActionButton to="/productos">Ver productos</ActionButton></template>
    </EmptyState>

    <div v-else class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div class="space-y-6">
        <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between gap-4 border-b border-gray-100 pb-4">
            <div>
              <h2 class="text-lg font-black text-gray-950">Productos</h2>
              <p class="text-sm text-gray-600">{{ cart.totalItems }} artículos · {{ formatWeight(totalWeight) }} kg estimados</p>
            </div>
            <RouterLink to="/carrito" class="text-sm font-bold text-red-700 hover:text-red-900">Editar carrito</RouterLink>
          </div>
          <div class="divide-y divide-gray-100">
            <article v-for="item in cart.items" :key="item.articulo.clave" class="grid gap-3 py-4 sm:grid-cols-[1fr_auto] sm:items-center">
              <div>
                <p class="font-bold text-gray-950">{{ item.articulo.nombre }}</p>
                <p class="mt-1 text-sm text-gray-600">{{ item.articulo.clave }} · {{ item.cantidad }} {{ item.articulo.unidad || 'UN' }}</p>
              </div>
              <div class="sm:text-right">
                <p class="text-sm text-gray-500">$ {{ money(item.precio_unitario) }} c/u</p>
                <p class="text-lg font-black text-gray-950">$ {{ money(item.subtotal) }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 class="text-lg font-black text-gray-950">Condiciones del pedido</h2>
          <div class="mt-5 grid gap-5 md:grid-cols-2">
            <label class="block">
              <span class="mb-2 block text-sm font-bold text-gray-700">Modalidad</span>
              <select v-model="modalidad" :disabled="actualizandoPrecios" class="h-11 w-full rounded-lg border border-gray-300 bg-white px-3 font-semibold focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100">
                <option value="retira">Retira en FASA</option>
                <option value="reparto">Reparto</option>
              </select>
            </label>
            <div>
              <span class="mb-2 block text-sm font-bold text-gray-700">Condición comercial</span>
              <div class="flex h-11 items-center rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold text-gray-800">
                {{ condicionPago ? `Condición ${condicionPago}` : 'Condición habitual de la cuenta' }}
              </div>
            </div>
            <div>
              <span class="mb-2 block text-sm font-bold text-gray-700">Impuestos</span>
              <div class="flex h-11 items-center rounded-lg border border-gray-200 bg-gray-50 px-3 text-sm font-semibold text-gray-800">
                {{ conImpuestos ? 'Precios con impuestos' : 'Precios sin impuestos' }}
              </div>
            </div>
            <div v-if="modalidad === 'reparto'" class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Ventas confirmará disponibilidad de reparto y datos finales de entrega con la información de tu cuenta.
            </div>
          </div>
          <label class="mt-5 block">
            <span class="mb-2 block text-sm font-bold text-gray-700">Observaciones</span>
            <textarea
              v-model.trim="observaciones"
              maxlength="1000"
              rows="4"
              placeholder="Referencias, horarios, aclaraciones de entrega u otra información para Ventas."
              class="w-full rounded-lg border border-gray-300 bg-white px-3 py-3 text-sm focus:border-red-600 focus:outline-none focus:ring-4 focus:ring-red-100"
            />
            <span class="mt-1 block text-right text-xs text-gray-500">{{ observaciones.length }}/1000</span>
          </label>
        </section>
      </div>

      <aside class="h-fit rounded-xl border border-gray-200 bg-white p-5 shadow-sm xl:sticky xl:top-24">
        <p class="text-sm font-bold uppercase tracking-wide text-red-700">Resumen</p>
        <div class="mt-4 flex items-end justify-between gap-4 border-b border-gray-100 pb-4">
          <span class="font-semibold text-gray-700">Total estimado</span>
          <strong class="text-2xl font-black text-gray-950">$ {{ money(cart.totalPrice) }}</strong>
        </div>
        <div class="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm leading-6 text-blue-950">
          <strong>No se realiza ningún pago online.</strong> Este envío genera una solicitud de pedido. Ventas FASA confirmará disponibilidad, precio final y condiciones.
        </div>
        <button
          type="button"
          :disabled="sending || actualizandoPrecios || !preciosActualizados || cart.items.length === 0"
          class="mt-5 inline-flex min-h-12 w-full items-center justify-center rounded-lg bg-red-700 px-5 py-3 text-sm font-black text-white shadow-sm transition hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-60"
          @click="sendOrder"
        >
          {{ sending ? 'ENVIANDO PEDIDO...' : actualizandoPrecios ? 'ACTUALIZANDO PRECIOS...' : 'ENVIAR PEDIDO A FASA' }}
        </button>
        <p v-if="errorMessage" class="mt-3 rounded-lg bg-red-50 p-3 text-sm font-semibold text-red-800">{{ errorMessage }}</p>
        <button v-if="!preciosActualizados && !actualizandoPrecios" type="button" class="mt-3 text-sm font-bold text-red-700 underline" @click="actualizarPrecios">Reintentar actualización de precios</button>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { cart } from '@/services/cart'
import ActionButton from '@/components/ui/ActionButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

const router = useRouter()
const modalidad = ref(localStorage.getItem('articulos_modalidad') || 'retira')
const savedImpuestos = localStorage.getItem('articulos_con_impuestos')
const conImpuestos = ref(savedImpuestos === null ? true : savedImpuestos === 'true')
const condicionPago = ref(localStorage.getItem('condicion_pago') || '')
const observaciones = ref('')
const sending = ref(false)
const errorMessage = ref('')
const actualizandoPrecios = ref(false)
const preciosActualizados = ref(false)

const actualizarPrecios = async () => {
  if (!cart.items.length) return
  actualizandoPrecios.value = true
  preciosActualizados.value = false
  errorMessage.value = ''
  try {
    await cart.refreshPrices({ modalidad: modalidad.value, con_impuestos: conImpuestos.value, condicion_pago: condicionPago.value })
    preciosActualizados.value = true
  } catch (error) {
    errorMessage.value = error.response?.data?.error || error.message || 'No se pudieron actualizar los precios.'
  } finally {
    actualizandoPrecios.value = false
  }
}
watch(modalidad, value => {
  localStorage.setItem('articulos_modalidad', value)
  actualizarPrecios()
})
onMounted(actualizarPrecios)

const itemWeight = item => {
  const qty = Number(item.cantidad) || 0
  const weight = Number(item.articulo.peso) || 0
  const mts2 = Number(item.articulo.mts2) || 0
  if ((item.articulo.campoa1 || '').toLowerCase() === 'a' && mts2 > 0) return (qty / mts2) * weight
  return qty * weight
}
const totalWeight = computed(() => cart.items.reduce((sum, item) => sum + itemWeight(item), 0))
const formatWeight = value => new Intl.NumberFormat('es-AR', { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(Number(value) || 0)
const money = value => new Intl.NumberFormat('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0)

const sendOrder = async () => {
  if (sending.value || cart.items.length === 0) return
  sending.value = true
  errorMessage.value = ''
  try {
    const result = await cart.checkout(null, {
      modalidad: modalidad.value,
      con_impuestos: conImpuestos.value,
      condicion_pago: condicionPago.value || undefined,
      observaciones: observaciones.value,
    })
    if (!result.success) {
      errorMessage.value = result.message || 'No se pudo enviar el pedido.'
      return
    }
    router.push(`/pedido-confirmado/${result.pedido?.id || ''}`)
  } finally {
    sending.value = false
  }
}
</script>
