// src/utils/storage.js

const PREFIX = 'dashboard_v2_';
const LEGACY_PREFIX = 'dashboard_';
const TTL = 5 * 60 * 1000; // 5 minutos en milisegundos

// Migración única: el caché viejo podía contener datos filtrados por cliente
// (se guardaban si el filtro cambiaba en medio de la recarga). Se purga.
try {
  Object.keys(localStorage)
    .filter(k => k.startsWith(LEGACY_PREFIX) && !k.startsWith(PREFIX) && k !== 'dashboard_cacheTime')
    .forEach(k => localStorage.removeItem(k));
  localStorage.removeItem('dashboard_cacheTime');
} catch (e) {
  // localStorage no disponible: se ignora
}

export const dashboardStorage = {
  // Guardar datos con marca de tiempo
    set(key, data) {
    const item = {
        data,
        timestamp: Date.now(),
    };
    try {
        localStorage.setItem(PREFIX + key, JSON.stringify(item));
        // También guardamos el tiempo general del caché
        localStorage.setItem('dashboard_cacheTime', item.timestamp);
    } catch (e) {
        console.warn('No se pudo guardar en localStorage:', e);
    }
    },

  // Obtener datos si no han expirado
  get(key) {
    try {
      const itemStr = localStorage.getItem(PREFIX + key);
      if (!itemStr) return null;

      const item = JSON.parse(itemStr);
      const now = Date.now();
      
      // Si han pasado más de TTL ms, se considera expirado
      if (now - item.timestamp > TTL) {
        localStorage.removeItem(PREFIX + key);
        return null;
      }

      return item.data;
    } catch (e) {
      console.warn('Error al leer de localStorage:', e);
      return null;
    }
  },

  // Limpiar datos (opcional)
  remove(key) {
    localStorage.removeItem(PREFIX + key);
  },

  // Limpiar todo del dashboard
  clear() {
    Object.keys(localStorage)
      .filter(k => k.startsWith(PREFIX))
      .forEach(k => localStorage.removeItem(k));
  }
};