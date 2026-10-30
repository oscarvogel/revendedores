// src/services/dashboard.js
import api from './api'

/**
 * Obtiene los KPIs del dashboard del cliente logueado
 * @returns {Promise} Respuesta con los KPIs
 */
export const getDashboardKpis = async () => {
  try {
    const response = await api.get('api/dashboard/kpis/')
    return response.data
  } catch (error) {
    console.error('Error al obtener KPIs del dashboard:', error)
    throw error
  }
}

/**
 * Obtiene los comprobantes del cliente logueado con paginación y filtros
 * @param {Object} params - Parámetros de filtro y paginación
 * @param {number} params.page - Número de página (default: 1)
 * @param {number} params.page_size - Tamaño de página (default: 20)
 * @param {string} params.fecha_desde - Fecha desde (formato: YYYY-MM-DD)
 * @param {string} params.fecha_hasta - Fecha hasta (formato: YYYY-MM-DD)
 * @param {string} params.codigo - Tipo de comprobante (F, D, R, C)
 * @returns {Promise} Respuesta con los comprobantes paginados
 */
export const getComprobantesCliente = async (params = {}) => {
  try {
    const queryParams = new URLSearchParams()
    
    // Agregar parámetros si existen
    if (params.page) queryParams.append('page', params.page)
    if (params.page_size) queryParams.append('page_size', params.page_size)
    if (params.fecha_desde) queryParams.append('fecha_desde', params.fecha_desde)
    if (params.fecha_hasta) queryParams.append('fecha_hasta', params.fecha_hasta)
    if (params.codigo) queryParams.append('codigo', params.codigo)
    
    const response = await api.get(`api/comprobantes/?${queryParams.toString()}`)
    return response.data
  } catch (error) {
    console.error('Error al obtener comprobantes:', error)
    throw error
  }
}

/**
 * Obtiene el detalle de un comprobante específico
 * @param {string} numeroComprobante - Número del comprobante
 * @returns {Promise} Respuesta con el detalle del comprobante
 */
export const getDetalleComprobante = async (numeroComprobante) => {
  try {
    const response = await api.get(`api/comprobantes/${numeroComprobante}/`)
    return response.data
  } catch (error) {
    console.error('Error al obtener detalle del comprobante:', error)
    throw error
  }
}

/** Descarga el PDF generado por FASA ERP para el comprobante del cliente. */
export const descargarComprobante = async (tipo, numeroComprobante) => {
  return api.get(`api/comprobantes/${encodeURIComponent(tipo)}/${encodeURIComponent(numeroComprobante)}/pdf/`, {
    responseType: 'blob',
    headers: { Accept: 'application/pdf' },
  })
}

