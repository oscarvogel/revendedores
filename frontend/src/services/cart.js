import { reactive } from 'vue';
import api from './api';

const cartStorageKey = () => {
    try {
        const user = JSON.parse(localStorage.getItem('user') || 'null');
        return user?.id != null ? `shopping_cart_user_${user.id}` : null;
    } catch { return null; }
};
let activeOwner = cartStorageKey();
let syncQueue = Promise.resolve();
const requireCurrentOwner = () => {
    if (!activeOwner || activeOwner !== cartStorageKey()) {
        throw new Error('La sesión cambió en otra pestaña. Actualizá la página.');
    }
};

// Función para cargar el carrito desde localStorage
const loadCartFromStorage = () => {
    try {
        const key = cartStorageKey();
        const stored = key && localStorage.getItem(key);
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
        const key = cartStorageKey();
        if (!key) return;
        localStorage.setItem(key, JSON.stringify({ items }));
        console.log('💾 Carrito guardado en localStorage:', items.length, 'items');
        
        // Sincronizar con el backend
        const snapshot = JSON.parse(JSON.stringify(items));
        syncQueue = syncQueue.then(() => {
            if (activeOwner === key && cartStorageKey() === key) return sincronizarConBackend(snapshot);
        });
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
        requireCurrentOwner();
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
        requireCurrentOwner();
        this.items = this.items.filter(item => item.articulo.clave !== articulo_clave);
        saveCartToStorage(this.items); // Guardar después de eliminar
    },

    updateQuantity(articulo_clave, cantidad) {
        requireCurrentOwner();
        const item = this.items.find(item => item.articulo.clave === articulo_clave);
        if (item) {
            item.cantidad = cantidad;
            item.subtotal = item.cantidad * item.precio_unitario;
            saveCartToStorage(this.items); // Guardar después de actualizar
        }
    },

    clear() {
        requireCurrentOwner();
        this.items = [];
        saveCartToStorage(this.items); // Guardar después de limpiar
    },

    reloadForUser() {
        activeOwner = cartStorageKey();
        this.items = loadCartFromStorage();
        this.checkoutIdempotencyKey = null;
    },

    async refreshPrices({ modalidad, con_impuestos, condicion_pago }) {
        requireCurrentOwner();
        const owner = cartStorageKey();
        const items = this.items.slice();
        const prices = await Promise.all(items.map(async (item) => {
            const response = await api.post('/api/consultar-precio/', {
                articulo_clave: item.articulo.clave, modalidad, con_impuestos,
                ...(condicion_pago ? { condicion_pago } : {}),
            });
            const price = Number(response.data?.articulo?.precio_lista);
            if (!response.data?.success || !Number.isFinite(price) || price <= 0) {
                throw new Error(`No se pudo actualizar el precio de ${item.articulo.clave}.`);
            }
            return price;
        }));
        if (!owner || owner !== cartStorageKey() || items.length !== this.items.length || items.some((item, index) => item !== this.items[index])) {
            throw new Error('El carrito cambió; volvé a actualizar los precios.');
        }
        items.forEach((item, index) => {
            item.precio_unitario = prices[index];
            item.subtotal = item.cantidad * prices[index];
        });
        saveCartToStorage(this.items);
    },

    checkoutInProgress: false,
    checkoutIdempotencyKey: null,

    async checkout(onProgress = null, overrides = {}) {
        requireCurrentOwner();
        if (this.items.length === 0) throw new Error('El carrito está vacío');
        if (this.checkoutInProgress) return { success: false, message: 'El pedido ya se está enviando. Esperá un momento.', pedido: null };
        const owner = cartStorageKey();
        if (!owner) return { success: false, message: 'Iniciá sesión para enviar el pedido.', pedido: null };
        this.checkoutInProgress = true;
        const submittedItems = this.items.map(item => ({ item, cantidad: Number(item.cantidad) }));
        try {
            if (onProgress) onProgress('Enviando pedido...');
            const modalidad = overrides.modalidad || localStorage.getItem('articulos_modalidad') || 'retira';
            const savedImpuestos = localStorage.getItem('articulos_con_impuestos');
            const con_impuestos = overrides.con_impuestos ?? (savedImpuestos === null ? true : savedImpuestos === 'true');
            const condicion_pago = overrides.condicion_pago || localStorage.getItem('condicion_pago');
            const pedidoData = {
                modalidad,
                con_impuestos,
                ...(condicion_pago ? { condicion_pago } : {}),
                ...(overrides.observaciones ? { observaciones: overrides.observaciones } : {}),
                items: this.items.map(item => ({
                    articulo: item.articulo.clave,
                    cantidad: item.cantidad,
                    precio_unitario: parseFloat(item.precio_unitario.toFixed(2)),
                })),
            };
            const pendingKey = `${owner}_checkout`;
            const signature = JSON.stringify({ ...pedidoData, items: pedidoData.items.map(({ articulo, cantidad }) => ({ articulo, cantidad })) });
            let pending;
            try { pending = JSON.parse(localStorage.getItem(pendingKey) || 'null'); } catch { pending = null; }
            if (!pending || pending.signature !== signature) {
                pending = { signature, key: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}` };
                localStorage.setItem(pendingKey, JSON.stringify(pending));
            }
            this.checkoutIdempotencyKey = pending.key;
            const response = await api.post('/api/pedidos/checkout/', pedidoData, {
                headers: { 'Idempotency-Key': this.checkoutIdempotencyKey },
            });
            const pedido = response.data;
            localStorage.removeItem(pendingKey);
            if (owner === cartStorageKey()) {
                this.items = this.items.flatMap(item => {
                    const sent = submittedItems.find(entry => entry.item === item);
                    if (!sent) return [item];
                    const remaining = Math.max(0, Number((Number(item.cantidad) - sent.cantidad).toFixed(3)));
                    if (!remaining) return [];
                    item.cantidad = remaining;
                    item.subtotal = remaining * item.precio_unitario;
                    return [item];
                });
                saveCartToStorage(this.items);
            }
            this.checkoutIdempotencyKey = null;
            return {
                success: true,
                message: pedido.idempotent_replay
                    ? 'El pedido ya había sido enviado y fue recuperado correctamente.'
                    : 'Pedido enviado correctamente.',
                pedido,
            };
        } catch (error) {
            const errorMessage = error.response?.data?.error || error.response?.data?.detail || error.message || 'No se pudo procesar tu pedido. Intenta de nuevo.';
            return { success: false, message: errorMessage, pedido: null, error };
        } finally {
            this.checkoutInProgress = false;
        }
    },
});

window.addEventListener('user-logged-in', () => cart.reloadForUser());
window.addEventListener('user-logged-out', () => cart.reloadForUser());
window.addEventListener('storage', event => {
    if (event.key === 'user' && activeOwner !== cartStorageKey()) window.location.reload();
});
