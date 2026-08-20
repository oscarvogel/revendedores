import { reactive, computed, watch } from 'vue';
import api from './api';

// Función para cargar el carrito desde localStorage
const loadCartFromStorage = () => {
    try {
        const stored = localStorage.getItem('shopping_cart');
        if (stored) {
            const parsed = JSON.parse(stored);
            console.log('📦 Carrito cargado desde localStorage:', parsed);
            return parsed.items || [];
        }
    } catch (error) {
        console.error('❌ Error al cargar carrito desde localStorage:', error);
    }
    return [];
};

// Función para guardar el carrito en localStorage
const saveCartToStorage = (items) => {
    try {
        localStorage.setItem('shopping_cart', JSON.stringify({ items }));
        console.log('💾 Carrito guardado en localStorage:', items.length, 'items');
        
        // Sincronizar con el backend
        sincronizarConBackend(items);
    } catch (error) {
        console.error('❌ Error al guardar carrito en localStorage:', error);
    }
};

// Función para sincronizar el carrito con el backend
const sincronizarConBackend = async (items) => {
    try {
        // Sincronizar siempre, incluso si el carrito está vacío
        // (para limpiar el carrito en el backend cuando se eliminen todos los items)
        const response = await api.post('/api/sincronizar-carrito/', { items });
        console.log('✅ Carrito sincronizado con backend:', response.data);
    } catch (error) {
        // No mostrar error al usuario, solo logear
        console.warn('⚠️ No se pudo sincronizar carrito con backend:', error.message);
    }
};

export const cart = reactive({
    items: loadCartFromStorage(), // Cargar items al iniciar
    
    get totalItems() {
        // Retorna la cantidad de items diferentes (no la suma de cantidades)
        return this.items.length;
    },

    get totalPrice() {
        return this.items.reduce((total, item) => total + item.subtotal, 0);
    },

    add(articulo, cantidad = 1) {
        const existingItem = this.items.find(item => item.articulo.clave === articulo.clave);
        if (existingItem) {
            existingItem.cantidad += cantidad;
            existingItem.subtotal = existingItem.cantidad * existingItem.precio_unitario;
        } else {
            const precio_unitario = articulo.precio_lista;
            this.items.push({
                articulo: articulo,
                cantidad: cantidad,
                precio_unitario: precio_unitario,
                subtotal: cantidad * precio_unitario,
            });
        }
        saveCartToStorage(this.items); // Guardar después de agregar
    },

    remove(articulo_clave) {
        this.items = this.items.filter(item => item.articulo.clave !== articulo_clave);
        saveCartToStorage(this.items); // Guardar después de eliminar
    },

    updateQuantity(articulo_clave, cantidad) {
        const item = this.items.find(item => item.articulo.clave === articulo_clave);
        if (item) {
            item.cantidad = cantidad;
            item.subtotal = item.cantidad * item.precio_unitario;
            saveCartToStorage(this.items); // Guardar después de actualizar
        }
    },

    clear() {
        this.items = [];
        saveCartToStorage(this.items); // Guardar después de limpiar
    },

    checkoutInProgress: false,
    checkoutIdempotencyKey: null,

    async checkout(onProgress = null) {
        if (this.items.length === 0) {
            throw new Error('El carrito está vacío');
        }
        if (this.checkoutInProgress) {
            return {
                success: false,
                message: 'El pedido ya se está enviando. Esperá un momento.',
                pedido: null,
            };
        }

        this.checkoutInProgress = true;
        if (!this.checkoutIdempotencyKey) {
            this.checkoutIdempotencyKey = globalThis.crypto?.randomUUID?.()
                || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }

        try {
            if (onProgress) onProgress('Enviando pedido...');
            const modalidad = localStorage.getItem('articulos_modalidad') || 'retira';
            const savedImpuestos = localStorage.getItem('articulos_con_impuestos');
            const con_impuestos = savedImpuestos === null ? true : savedImpuestos === 'true';
            const condicion_pago = localStorage.getItem('condicion_pago');
            const pedidoData = {
                modalidad,
                con_impuestos,
                ...(condicion_pago ? { condicion_pago } : {}),
                items: this.items.map(item => ({
                    articulo: item.articulo.clave,
                    cantidad: item.cantidad,
                    precio_unitario: parseFloat(item.precio_unitario.toFixed(2)),
                })),
            };

            const response = await api.post('/api/pedidos/checkout/', pedidoData, {
                headers: { 'Idempotency-Key': this.checkoutIdempotencyKey },
            });
            const pedido = response.data;
            this.items = [];
            saveCartToStorage(this.items);
            this.checkoutIdempotencyKey = null;

            return {
                success: true,
                message: pedido.idempotent_replay
                    ? 'El pedido ya había sido enviado y fue recuperado correctamente.'
                    : 'Pedido enviado correctamente.',
                pedido,
            };
        } catch (error) {
            const errorMessage = error.response?.data?.error
                || error.response?.data?.detail
                || error.message
                || 'No se pudo procesar tu pedido. Intenta de nuevo.';
            return {
                success: false,
                message: errorMessage,
                pedido: null,
                error,
            };
        } finally {
            this.checkoutInProgress = false;
        }
    },
});