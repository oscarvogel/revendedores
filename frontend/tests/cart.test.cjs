const { test } = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')
const fs = require('node:fs')
const path = require('node:path')

async function makeCart() {
  const values = new Map()
  const listeners = {}
  const calls = []
  const localStorage = {
    getItem: k => values.get(k) ?? null,
    setItem: (k, v) => values.set(k, String(v)),
    removeItem: k => values.delete(k),
  }
  const api = { post: async (url, data, options) => {
    calls.push({ url, data, options })
    if (url.includes('consultar-precio')) return { data: { success: true, articulo: { precio_lista: 25 } } }
    if (url.includes('checkout')) return { data: { id: 1 } }
    return { data: {} }
  } }
  const window = { addEventListener: (name, fn) => { listeners[name] = fn } }
  const context = vm.createContext({ localStorage, window, console: { log() {}, warn() {}, error() {} }, crypto: { randomUUID: () => 'test-key' } })
  const module = new vm.SourceTextModule(fs.readFileSync(path.join(__dirname, '../src/services/cart.js'), 'utf8'), { context })
  await module.link(async specifier => specifier === 'vue'
    ? new vm.SyntheticModule(['reactive'], function () { this.setExport('reactive', value => value) }, { context })
    : new vm.SyntheticModule(['default'], function () { this.setExport('default', api) }, { context }))
  await module.evaluate()
  return { cart: module.namespace.cart, localStorage, listeners, calls, api }
}

test('cada usuario recupera solo su propio carrito en el mismo navegador', async () => {
  const { cart, localStorage, listeners } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  cart.add({ clave: 'A', precio_lista: 10 }, 2)
  localStorage.removeItem('user')
  listeners['user-logged-out']()
  assert.equal(cart.items.length, 0)
  localStorage.setItem('user', JSON.stringify({ id: 2 }))
  listeners['user-logged-in']()
  assert.equal(cart.items.length, 0)
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  assert.equal(cart.items[0].articulo.clave, 'A')
})

test('actualiza precios con la modalidad elegida antes del pedido', async () => {
  const { cart, localStorage, listeners, calls } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  cart.add({ clave: 'A', precio_lista: 10 }, 2)
  await cart.refreshPrices({ modalidad: 'reparto', con_impuestos: true })
  assert.equal(cart.totalPrice, 50)
  assert.equal(calls.find(c => c.url.includes('consultar-precio')).data.modalidad, 'reparto')
})

test('un reintento del mismo pedido conserva la clave luego de recargar el carrito', async () => {
  const { cart, localStorage, listeners, calls, api } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  cart.add({ clave: 'A', precio_lista: 10 }, 2)
  const originalPost = api.post
  let attempt = 0
  api.post = async (...args) => {
    if (args[0].includes('checkout') && attempt++ === 0) {
      calls.push({ url: args[0], options: args[2] })
      throw new Error('Conexión interrumpida')
    }
    return originalPost(...args)
  }
  assert.equal((await cart.checkout()).success, false)
  cart.reloadForUser()
  assert.equal((await cart.checkout()).success, true)
  const attempts = calls.filter(c => c.url.includes('checkout'))
  assert.equal(attempts[0].options.headers['Idempotency-Key'], attempts[1].options.headers['Idempotency-Key'])
})

test('al cambiar el usuario en otra pestaña no guarda el carrito previo en la cuenta nueva', async () => {
  const { cart, localStorage, listeners } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  cart.add({ clave: 'A', precio_lista: 10 }, 1)
  localStorage.setItem('user', JSON.stringify({ id: 2 }))
  try { cart.add({ clave: 'B', precio_lista: 20 }, 1) } catch {}
  const stored = JSON.parse(localStorage.getItem('shopping_cart_user_2') || '{"items":[]}')
  assert.equal(stored.items.some(item => item.articulo.clave === 'A'), false)
})

test('el envío no elimina productos agregados mientras se procesa el pedido', async () => {
  const { cart, localStorage, listeners, api } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  cart.add({ clave: 'A', precio_lista: 10 }, 1)
  let finish
  const originalPost = api.post
  api.post = (...args) => args[0].includes('checkout')
    ? new Promise(resolve => { finish = () => resolve({ data: { id: 1 } }) })
    : originalPost(...args)
  const pending = cart.checkout()
  cart.add({ clave: 'B', precio_lista: 20 }, 1)
  finish()
  assert.equal((await pending).success, true)
  assert.equal(cart.items.some(item => item.articulo.clave === 'B'), true)
  assert.equal(cart.items.some(item => item.articulo.clave === 'A'), false)
})

test('sincroniza cambios del carrito en orden y conserva la última versión', async () => {
  const { cart, localStorage, listeners, api } = await makeCart()
  localStorage.setItem('user', JSON.stringify({ id: 1 }))
  listeners['user-logged-in']()
  const syncs = []
  api.post = (url, data) => url.includes('sincronizar-carrito')
    ? new Promise(resolve => syncs.push({ data, finish: () => resolve({ data: {} }) }))
    : Promise.resolve({ data: {} })
  cart.add({ clave: 'A', precio_lista: 10 }, 1)
  cart.add({ clave: 'B', precio_lista: 20 }, 1)
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(syncs.length, 1)
  assert.equal(syncs[0].data.items.length, 1)
  syncs[0].finish()
  await new Promise(resolve => setImmediate(resolve))
  assert.equal(syncs.length, 2)
  assert.equal(syncs[1].data.items.length, 2)
  syncs[1].finish()
})
