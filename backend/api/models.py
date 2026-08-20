from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
# Create your models here.
    
LISTA_CLIENTE = [
        (' ', 'Todos'),
        ('1', 'Lista 1'),
        ('4', 'Lista 4')
    ]

class BonificacionCliente(models.Model):
    cliente = models.ForeignKey('Cliente', on_delete=models.CASCADE)
    desde_articulo = models.CharField(max_length=8, verbose_name="Desde Artículo")
    hasta_articulo = models.CharField(max_length=8, verbose_name="Hasta Artículo")
    bonificacion = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = 'Bonificación por Cliente'
        verbose_name_plural = 'Bonificaciones por Cliente'

    def __str__(self):
        return f"Bonificación para {self.cliente.nombre} desde {self.desde_articulo} hasta {self.hasta_articulo}: {self.bonificacion}%"
    
class Articulos(models.Model):
    clave = models.CharField(max_length=8, primary_key=True)
    unidad = models.CharField(max_length=8)
    nombre = models.CharField(max_length=50)
    peso = models.DecimalField(max_digits=12, decimal_places=2)
    espesor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mts2 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio1 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Lista 1", default=0)
    precio4 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Lista 4", default=0)
    reparto = models.CharField(max_length=2, verbose_name="Reparto", default='')
    redferre = models.CharField(max_length=1, verbose_name="Red Ferreteria", default='')
    tiporeparto = models.CharField(max_length=1, verbose_name="Tipo Reparto", default='')
    campoa1 = models.CharField(max_length=1, verbose_name="Campo A1", default='')
    reducida = models.CharField(max_length=1, verbose_name="Reducida", default='')
    preciopub = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Publico", default=0)
    recargo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Recargo", default=0)
    estado = models.CharField(max_length=1, verbose_name="Estado", default='')
    pblret1 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Publico Retir L1")
    pblrep1 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Publico Reparto L1")
    pblret4 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Publico Retira L4")
    pblrep4 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Publico Reparto L4")
    ultact = models.DateField(verbose_name="Ultima Actualizacion")
    imagen = models.ImageField(upload_to='articulos/', blank=True, null=True)
    visible = models.CharField(max_length=1, verbose_name="Visible")
    grupo = models.CharField(max_length=3, verbose_name="Grupo", default='')
    stock = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Stock", default=0)
    formula = models.CharField(max_length=20, verbose_name="Formula", default='')
    descripcion = models.CharField(max_length=100)
    discontinuado = models.CharField(max_length=1, verbose_name="Discontinuado", default='')
    oferta = models.CharField(max_length=1, verbose_name="Oferta", default='')
    vencimiento_oferta = models.DateField(verbose_name="Vencimiento Oferta", null=True, blank=True)
    empresa_id = models.IntegerField(default=1)
    
    class Meta:
        verbose_name = 'Articulo'
        verbose_name_plural = 'Articulos'

    def __str__(self):
        return self.nombre


class FormaPago(models.Model):
    id = models.CharField(primary_key=True, max_length=4)
    nombre = models.CharField(max_length=50)
    lista = models.CharField(max_length=1, choices=LISTA_CLIENTE, blank=True, null=True)
    punitorio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Punitorio", default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Descuento", default=0)

    class Meta:
        verbose_name = 'Forma de Pago'
        verbose_name_plural = 'Formas de Pago'

    def __str__(self):
        return self.nombre    
    
class Localidades(models.Model):
    
    codigo = models.CharField(max_length=4, primary_key=True)
    nombre = models.CharField(max_length=50)
    distancia = models.IntegerField(default=0)
    fletep1 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Flete % Lista 1")
    fletetn1 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Flete TN Lista 1")
    fletep4 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Flete % Lista 4")
    fletetn4 = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Flete TN Lista 4")
    reparto = models.CharField(max_length=1, default='', blank=True, verbose_name="Localidad con Reparto")

    class Meta:
        verbose_name = 'Localidad'
        verbose_name_plural = 'Localidades'
    
    def __str__(self):
        return self.nombre
    

class Cliente(models.Model):
    TIPO_RESPONSABILIDAD_IVA = [
        ('C', 'Responsable Inscripto'),
        ('F', 'Consumidor Final'),
        ('M', 'Monotributista'),
        ('E', 'Exento'),
    ]

    REGIMEN_PERCEPCION = [
        ('', 'No alcanzado'),
        ('60', 'Régimen de IIBB'),
    ]


    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cliente')
    numero_cliente = models.CharField(max_length=5, unique=True)
    lista_precio = models.CharField(max_length=1, choices=LISTA_CLIENTE)
    nombre = models.CharField(max_length=100)
    codigo_localidad = models.ForeignKey(Localidades, on_delete=models.CASCADE)
    condicion_pago = models.ForeignKey(FormaPago, on_delete=models.CASCADE)
    tipo_responsable_iva = models.CharField(max_length=2, choices=TIPO_RESPONSABILIDAD_IVA)
    regimen_percepcion = models.CharField(max_length=2, choices=REGIMEN_PERCEPCION, blank=True)
    cuit = models.CharField(max_length=13, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True)

    def save(self, *args, **kwargs):
        """Formatea el numero_cliente con ceros a la izquierda (00040)."""
        if self.numero_cliente:
            # Remover espacios y convertir a string
            numero = str(self.numero_cliente).strip()
            # Si es un número, rellenar con ceros a la izquierda
            if numero.isdigit():
                self.numero_cliente = numero.zfill(5)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.numero_cliente} - {self.user.get_full_name() or self.user.username}"        

class Favorito(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favoritos')
    articulo = models.ForeignKey(Articulos, on_delete=models.CASCADE, related_name='favoritos')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'articulo')
        verbose_name = 'Favorito'
        verbose_name_plural = 'Favoritos'

    def __str__(self):
        return f'{self.user.username} - {self.articulo.nombre}'        

class Busqueda(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='busquedas')
    query = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Búsqueda'
        verbose_name_plural = 'Búsquedas'
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.user.username}: "{self.query}" ({self.timestamp.strftime("%Y-%m-%d %H:%M")})'

class Pedido(models.Model):
    ESTADO_PEDIDO = [
        ('PENDIENTE', 'Pendiente'),
        ('CONFIRMADO', 'Confirmado'),
        ('EN_PROCESO', 'En Proceso'),
        ('PREPARADO', 'Preparado'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]

    MODALIDAD_CHOICES = [
        ('retira', 'Retira'),
        ('reparto', 'Reparto'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pedidos')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_PEDIDO, default='PENDIENTE')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    modalidad = models.CharField(max_length=10, choices=MODALIDAD_CHOICES, default='retira')
    con_impuestos = models.BooleanField(default=True)
    condicion_pago = models.ForeignKey(
        FormaPago,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos',
    )
    cliente_snapshot = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)

    def __str__(self):
        return f"Pedido #{self.id} - {self.user.username} ({self.get_estado_display()})"

    def calcular_total(self):
        """Calcula el total del pedido sumando los subtotales de los items."""
        self.total = sum(item.subtotal for item in self.items.all())
        self.save()

class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    articulo = models.ForeignKey(Articulos, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        """Calcula el subtotal antes de guardar."""
        self.subtotal = self.precio_unitario * self.cantidad
        super().save(*args, **kwargs)

    def calcular_peso(self):
        """Calcula el peso respetando cantidades en m²/cajas."""
        cantidad = Decimal(str(self.cantidad))
        peso_unitario = Decimal(str(self.articulo.peso or 0))
        mts2 = Decimal(str(self.articulo.mts2 or 0))
        if (self.articulo.campoa1 or '').lower() == 'a' and mts2 > 0:
            return (cantidad / mts2) * peso_unitario
        return cantidad * peso_unitario

    def __str__(self):
        return f"{self.cantidad} x {self.articulo.nombre} en Pedido #{self.pedido.id}"        

class RegistroSesion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    inicio_sesion = models.DateTimeField(default=timezone.now)
    fin_sesion = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    duracion = models.DurationField(null=True, blank=True)  # Se puede calcular
    last_activity = models.DateTimeField(default=timezone.now)  # Última actividad registrada
    
    def calcular_duracion(self):
        if self.fin_sesion and self.inicio_sesion:
            return self.fin_sesion - self.inicio_sesion
        return None

    def save(self, *args, **kwargs):
        self.duracion = self.calcular_duracion()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario.username} - {self.inicio_sesion} ({self.duracion or 'Activa'})"


class ConsultaPrecio(models.Model):
    """Modelo para registrar consultas de precios de artículos."""
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultas_precio')
    articulo = models.ForeignKey(Articulos, on_delete=models.CASCADE, related_name='consultas_precio')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Consulta de Precio'
        verbose_name_plural = 'Consultas de Precios'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['usuario', 'fecha_hora']),
            models.Index(fields=['articulo', 'fecha_hora']),
        ]

    def __str__(self):
        return f"{self.usuario.username} consultó precio de {self.articulo.clave} - {self.fecha_hora}"    


class ExportEvent(models.Model):
    """Registra acciones de exportación realizadas por los usuarios (por ejemplo: exportar favoritos)."""
    TIPO_CHOICES = [
        ('favoritos', 'Exportar Favoritos'),
        ('carrito', 'Exportar Carrito'),
        ('otros', 'Otros'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_events')
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default='favoritos')
    parametros = models.JSONField(null=True, blank=True, help_text='Parámetros usados para la exportación (modalidad, con_impuestos, etc.)')
    total_items = models.IntegerField(default=0, help_text='Cantidad de items incluidos en la exportación')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento de Exportación'
        verbose_name_plural = 'Eventos de Exportación'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Exportación {self.tipo} por {self.usuario.username} ({self.total_items}) - {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"


class ArticuloVista(models.Model):
    TIPO_CHOICES = [
        ('oferta', 'Oferta'),
        ('discontinuado', 'Discontinuado'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articulos_vistos')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        verbose_name = 'Vista de Articulo (Oferta/Discontinuado)'
        verbose_name_plural = 'Vistas de Articulos (Oferta/Discontinuado)'
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.usuario.username} - {self.tipo} - {self.fecha_hora.strftime('%Y-%m-%d %H:%M')}"


class CarritoTemporal(models.Model):
    """
    Modelo para almacenar carritos temporales de clientes.
    Se sincroniza con localStorage del frontend.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carrito_temporal')
    articulo = models.ForeignKey(Articulos, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, help_text="Cantidad o m² según el tipo de artículo")
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_agregado = models.DateTimeField(auto_now_add=True)
    fecha_modificado = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Carrito Temporal'
        verbose_name_plural = 'Carritos Temporales'
        ordering = ['-fecha_modificado']
        unique_together = ['user', 'articulo']  # Un usuario no puede tener el mismo artículo duplicado
        indexes = [
            models.Index(fields=['user', 'fecha_modificado']),
            models.Index(fields=['fecha_modificado']),
        ]

    def __str__(self):
        return f"Carrito de {self.user.username}: {self.articulo.nombre} x {self.cantidad}"
    
    def calcular_peso(self):
        """Calcula el peso total del item según el tipo de artículo."""
        campoa1 = (self.articulo.campoa1 or '').lower()
        peso_unitario = float(self.articulo.peso) or 0
        
        if campoa1 == 'a' and float(self.articulo.mts2) > 0:
            # Tipo A con m²: peso = (cantidad m² / m² por caja) × peso por caja
            cajas = float(self.cantidad) / float(self.articulo.mts2)
            return cajas * peso_unitario
        
        # Otros tipos: peso = cantidad × peso unitario
        return float(self.cantidad) * peso_unitario


class CuentaCorrienteCliente(models.Model):
    id = models.AutoField(primary_key=True)  # Campo ID autoincrementable
    cliente = models.CharField(max_length=5)
    nombre = models.CharField(max_length=45)
    neto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    fecha = models.DateField()
    fechaven = models.DateField(db_column='FECHAVEN')
    fecha1venc = models.DateField(db_column='FECHA1VENC')
    pago = models.CharField(max_length=2, default='00')
    forma_pago = models.CharField(max_length=40)
    codigo = models.CharField(max_length=1)
    clase = models.CharField(max_length=1, default='B')
    numero = models.CharField(max_length=12, default='0')

    class Meta:
        db_table = 'cuenta_corriente_clientes'
        verbose_name = 'Cuenta Corriente Cliente'
        verbose_name_plural = 'Cuentas Corrientes Clientes'
        ordering = ['-fecha', '-numero']  # Ordenar por fecha descendente por defecto
        managed = False  # Este modelo no gestionará la creación de la tabla

    def __str__(self):
        return f"{self.cliente} - {self.numero} - {self.nombre}"

class Factura(models.Model):
    cliente = models.CharField(max_length=5)
    nombre = models.CharField(max_length=45)
    neto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    neto_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    precio = models.DecimalField(max_digits=13, decimal_places=3, default=0.000)
    unitario = models.DecimalField(max_digits=13, decimal_places=3, default=0.000)
    cantidad = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    fecha = models.DateField()
    neto_renglon = models.DecimalField(max_digits=33, decimal_places=11, null=True, blank=True, db_column='netoRenglon')
    total = models.DecimalField(max_digits=23, decimal_places=7, default=0.0000000)
    percepcion_dgr = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, db_column='percepcionDGR')
    dgrdetalle = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    localidad = models.CharField(max_length=4)
    codigo = models.CharField(max_length=2, default='F')
    lista = models.CharField(max_length=1)
    clave = models.CharField(max_length=8)
    reparto = models.CharField(max_length=8)
    comp = models.CharField(max_length=12, default='0')
    regiva = models.CharField(max_length=4)
    idmovi = models.IntegerField(default=0)
    clase = models.CharField(max_length=1)
    vendedor = models.CharField(max_length=2)
    flete = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    nota = models.CharField(max_length=50)
    unidad = models.CharField(max_length=8)
    pago = models.CharField(max_length=2, default='00')
    cuotapago = models.IntegerField(default=1)
    fechaven = models.DateField()
    fecha1venc = models.DateField()
    fletetransp = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    boni = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    costo = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    introduccion = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sucursal = models.IntegerField(default=0)
    contado = models.CharField(max_length=1, default='S')
    idstockve = models.IntegerField(default=0)
    detext = models.TextField(null=True, blank=True)
    aliciva = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    descad = models.CharField(max_length=40)
    procesado = models.BooleanField(default=False)
    pagoant = models.BooleanField(default=False)
    item = models.CharField(max_length=3)
    gastotar = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    des1 = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    punitorio = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    reparte = models.CharField(max_length=1)
    monto_comision = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    porcentaje_comisionista = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    comisionista = models.CharField(max_length=5)
    comision_conciliada = models.BooleanField(default=False)
    mensaje4 = models.CharField(max_length=120)
    empresa_id = models.IntegerField(default=1)
    forma_pago = models.CharField(max_length=30, default='')
    nombre_vendedor = models.CharField(max_length=50, default='')
    nombre_localidad = models.CharField(max_length=50, default='')

    class Meta:
        db_table = 'facturas'
        managed = False  # ¡Importante! Django no creará ni migrará esta tabla
        # Si necesitas orden predeterminado:
        # ordering = ['-fecha', 'comp']

    def __str__(self):
        return f"{self.cliente} - {self.nombre} - {self.comp}"    

class Cobranzas(models.Model):
    tipo = models.CharField(max_length=1, null=True, blank=True)
    recibo = models.CharField(max_length=12, null=True, blank=True)
    codigo = models.CharField(max_length=1, null=True, blank=True)
    clase = models.CharField(max_length=1, null=True, blank=True)
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    detalle = models.CharField(max_length=40, null=True, blank=True)
    banco = models.CharField(max_length=20, null=True, blank=True)
    numero = models.CharField(max_length=12, null=True, blank=True)
    vence = models.DateField(null=True, blank=True, default=None)
    impentra = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, default=0.00)
    comp = models.CharField(max_length=12, null=True, blank=True)

    class Meta:
        db_table = 'cobranzas'
        managed = False  # Indica que Django no debe gestionar esta tabla/vista    
    
class LinkOpen(models.Model):
    """Registra aperturas/redirecciones de links enviados en campañas/emails.

    Se usa un token firmado para identificar destinatario/campaña sin exponer IDs.
    """
    token = models.CharField(max_length=255, db_index=True)
    recipient_email = models.EmailField(null=True, blank=True)
    campaign = models.CharField(max_length=100, null=True, blank=True)
    target_url = models.URLField(max_length=2000)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    referer = models.CharField(max_length=2000, null=True, blank=True)
    opened_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Apertura de Link'
        verbose_name_plural = 'Aperturas de Links'
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.recipient_email or 'anon'} {self.opened_at.isoformat()}"


class ShortTrackingLink(models.Model):
    """Guarda un código corto que apunta a un token de tracking firmado."""

    code = models.CharField(max_length=12, unique=True, db_index=True)
    token = models.CharField(max_length=255, db_index=True)
    recipient_email = models.EmailField(null=True, blank=True)
    campaign = models.CharField(max_length=100, null=True, blank=True)
    target_url = models.URLField(max_length=2000)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Link Corto de Tracking'
        verbose_name_plural = 'Links Cortos de Tracking'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} -> {self.target_url}"


class BotConversationLog(models.Model):
    ORIGEN_CHOICES = [
        ('chat_local', 'Chat local'),
        ('whatsapp', 'WhatsApp'),
        ('api', 'API'),
    ]
    ESTADO_CHOICES = [
        ('ok', 'OK'),
        ('ambiguous', 'Ambiguo'),
        ('not_found', 'No encontrado'),
        ('fallback', 'Fallback'),
        ('error', 'Error'),
    ]

    fecha_hora = models.DateTimeField(default=timezone.now, db_index=True)
    origen = models.CharField(max_length=30, choices=ORIGEN_CHOICES, db_index=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='bot_logs')
    telefono = models.CharField(max_length=30, null=True, blank=True, db_index=True)
    mensaje_usuario = models.TextField()
    respuesta_bot = models.TextField(blank=True)
    intencion = models.CharField(max_length=50, default='fallback', db_index=True)
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='ok', db_index=True)
    contexto = models.JSONField(default=dict, blank=True)
    error_tecnico = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Log de Conversacion Bot'
        verbose_name_plural = 'Logs de Conversaciones Bot'
        ordering = ['-fecha_hora']
        indexes = [
            models.Index(fields=['origen', 'fecha_hora']),
            models.Index(fields=['intencion', 'estado']),
        ]

    def __str__(self):
        actor = self.usuario.username if self.usuario else self.telefono or 'anon'
        return f"{self.origen} - {actor} - {self.fecha_hora:%Y-%m-%d %H:%M}"
        
