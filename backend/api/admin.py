from django.contrib import admin
from .models import BonificacionCliente, Cliente, FormaPago, Localidades, Articulos, ArticuloDestacado, ArticuloOculto, ExportEvent, LinkOpen, OfertaEnviada

# Register your models here.

class ArticulosAdmin(admin.ModelAdmin):
    list_display = ('clave', 'nombre', 'unidad', 'precio1', 'precio4', 'stock')
    search_fields = ('nombre',) # Add search by name
    list_filter = ('grupo',)


class ArticuloDestacadoAdmin(admin.ModelAdmin):
    list_display = ('articulo', 'fecha_creacion', 'creado_por')
    search_fields = ('articulo__clave', 'articulo__nombre')
    raw_id_fields = ('articulo',)

class LocalidadesAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'distancia')
    search_fields = ('nombre',)

class BonificacionClienteAdmin(admin.ModelAdmin):
    list_display = ('cliente', 'desde_articulo', 'hasta_articulo', 'bonificacion')
    search_fields = ('cliente__nombre', 'desde_articulo', 'hasta_articulo')
    list_filter = ('cliente',)
    raw_id_fields = ('cliente',)

class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_localidad', 'lista_precio', 'recibe_ofertas_email')
    search_fields = ('nombre', 'numero_cliente')
    list_filter = ('lista_precio', 'recibe_ofertas_email')
    raw_id_fields = ('codigo_localidad','user')

admin.site.register(Cliente, ClienteAdmin)


class OfertaEnviadaAdmin(admin.ModelAdmin):
    list_display = ('enviado_en', 'cliente', 'articulo', 'consultas', 'email')
    search_fields = ('cliente__nombre', 'cliente__numero_cliente', 'articulo__clave', 'articulo__nombre')
    raw_id_fields = ('cliente', 'articulo')
    date_hierarchy = 'enviado_en'


admin.site.register(OfertaEnviada, OfertaEnviadaAdmin)
    
admin.site.register(FormaPago)
admin.site.register(Localidades, LocalidadesAdmin)
admin.site.register(Articulos, ArticulosAdmin)
admin.site.register(ArticuloDestacado, ArticuloDestacadoAdmin)


class ArticuloOcultoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'patron', 'motivo', 'fecha_creacion', 'creado_por')
    search_fields = ('patron', 'motivo')
    list_filter = ('tipo',)


admin.site.register(ArticuloOculto, ArticuloOcultoAdmin)
admin.site.register(BonificacionCliente, BonificacionClienteAdmin)


class ExportEventAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'total_items', 'fecha_hora', 'ip_address')
    search_fields = ('usuario__username', 'tipo')
    list_filter = ('tipo', 'fecha_hora')

admin.site.register(ExportEvent, ExportEventAdmin)


class LinkOpenAdmin(admin.ModelAdmin):
    list_display = ('recipient_email', 'campaign', 'target_url', 'ip_address', 'opened_at')
    search_fields = ('recipient_email', 'campaign')
    list_filter = ('campaign', 'opened_at')


admin.site.register(LinkOpen, LinkOpenAdmin)
