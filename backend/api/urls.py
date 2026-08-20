from django.urls import path, include
from . import views
from . import bot_views
from . import staff_views
from rest_framework.routers import DefaultRouter

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from api.serializers import CookieTokenRefreshView, CustomTokenObtainPairSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

router = DefaultRouter()
router.register(r'articulos', views.ArticuloViewSet)
router.register(r'favoritos', views.FavoritoViewSet, basename='favorito')
router.register(r'busquedas', views.BusquedaViewSet, basename='busqueda')
router.register(r'pedidos', views.PedidoViewSet, basename='pedido')

urlpatterns = [
    path('', include(router.urls)),
    # path('login/', views.user_login, name='user_login'),
    path('logout/', views.user_logout, name='user_logout'),
    path('profile/', views.update_profile, name='update_profile'),  
    path('formas-pago/', views.FormasPagoView.as_view(), name='formas-pago'),
    path('keep-alive/', views.keep_alive, name='keep_alive'),
    path('track-articulos-view/', views.track_articulos_view, name='track-articulos-view'),
    path('track/', views.track_redirect, name='track_redirect'),
    path('track-pixel/', views.track_pixel, name='track_pixel'),
    path('track-preview/', views.track_preview, name='track_preview'),
    path('track-token/', views.track_token, name='track_token'),
    path('track-shorten/', views.track_shorten, name='track_shorten'),
    path('t/<str:code>/', views.track_short_redirect, name='track_short_redirect_api'),
    path('whatsapp/webhook/', bot_views.whatsapp_webhook, name='whatsapp-webhook'),
    path('bot/test-chat/', bot_views.test_chat, name='bot-test-chat'),
    path('consultar-precio/', views.consultar_precio, name='consultar_precio'),
    path('exportar-favoritos/', views.exportar_favoritos, name='exportar_favoritos'),
    path('dashboard/kpis/', views.dashboard_kpis, name='dashboard_kpis'),
    path('comprobantes/', views.comprobantes_cliente, name='comprobantes_cliente'),
    path('comprobantes/<str:numero_comprobante>/', views.detalle_comprobante, name='detalle_comprobante'),
    path('sincronizar-carrito/', staff_views.sincronizar_carrito, name='sincronizar-carrito'),
    # JWT
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),    
    # NOTE: api/ is already prefixed in the project urls (path('api/', include('api.urls'))),
    # so this route must NOT include an extra 'api/' segment or it will be served at /api/api/token/refresh/.
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    # Staff Dashboard URLs
    path('staff/most-favorited-products/', staff_views.MostFavoritedProductsView.as_view(), name='most-favorited-products'),
    path('staff/sales-summary/', staff_views.SalesSummaryView.as_view(), name='sales-summary'),
    path('staff/most-searched-words/', staff_views.MostSearchedWordsView.as_view(), name='most-searched-words'),
    path('staff/daily-sales/', staff_views.DailySalesView.as_view(), name='daily-sales'),
    path('staff/session-metrics/', staff_views.session_metrics, name='session-metrics'),
    path('staff/ingresos-dispositivo/', staff_views.ingresos_por_dispositivo, name='ingresos-dispositivo'),
    path('staff/sessions/', staff_views.sessions_today_detail, name='sessions-today-detail'),
    path('staff/exports/', staff_views.exports_list, name='staff-exports'),
    path('staff/exports-summary/', staff_views.exports_summary, name='staff-exports-summary'),
    path('staff/articulos-vistas/', staff_views.articulos_vistas_summary, name='staff-articulos-vistas'),
    path('staff/articulos-mas-consultados/', staff_views.articulos_mas_consultados, name='articulos-mas-consultados'),
    path('staff/usuarios/', staff_views.obtener_usuarios, name='obtener-usuarios'),
    path('staff/carritos/', staff_views.obtener_carritos_clientes, name='obtener-carritos-clientes'),
    path('staff/tracking/campaigns/', staff_views.tracking_campaigns, name='staff-tracking-campaigns'),
    path('staff/tracking/kpis/', staff_views.tracking_kpis, name='staff-tracking-kpis'),
    path('staff/tracking/opens/', staff_views.tracking_opens, name='staff-tracking-opens'),
    path('staff/bot/report/', staff_views.bot_report, name='staff-bot-report'),
    
    # Staff Gestión de Pedidos URLs
    path('staff/pedidos/', staff_views.StaffPedidosView.as_view(), name='staff-pedidos'),
    path('staff/pedidos/<int:pk>/', staff_views.StaffPedidosView.as_view(), name='staff-pedido-detail'),
    path('staff/pedidos/<int:pedido_id>/reenviar-email/', staff_views.reenviar_email_pedido, name='reenviar-email-pedido'),
    path('staff/pedidos/resumen/', staff_views.resumen_pedidos_staff, name='resumen-pedidos-staff'),
    
    # Staff Gestión de Clientes URLs
    path('staff/clientes/', staff_views.StaffClientesView.as_view(), name='staff-clientes'),
    path('staff/clientes/<int:pk>/', staff_views.StaffClientesView.as_view(), name='staff-cliente-detail'),
    path('staff/clientes/datos-auxiliares/', staff_views.obtener_datos_auxiliares_cliente, name='datos-auxiliares-cliente'),
]
