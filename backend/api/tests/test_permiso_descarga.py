from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from api.models import Cliente, FormaPago, Localidades

class PermisoDescargaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cliente')
        loc = Localidades.objects.create(codigo='9999', nombre='Prueba')
        pago = FormaPago.objects.create(id='99', nombre='Contado', descuento=0, punitorio=0)
        self.cliente = Cliente.objects.create(user=self.user, numero_cliente='99999', nombre='Cliente', lista_precio='1', codigo_localidad=loc, condicion_pago=pago, tipo_responsable_iva='C')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_cliente_nuevo_no_tiene_permiso(self):
        self.assertFalse(self.cliente.puede_descargar_lista)
        self.assertEqual(self.api.get('/api/exportar-favoritos/').status_code, 403)
        self.assertFalse(self.api.get('/api/permiso-descarga-lista/').data['puede_descargar_lista'])

    def test_cliente_habilitado_puede_acceder(self):
        self.cliente.puede_descargar_lista = True
        self.cliente.save()
        self.assertTrue(self.api.get('/api/permiso-descarga-lista/').data['puede_descargar_lista'])
        self.assertEqual(self.api.get('/api/exportar-favoritos/').status_code, 404)  # sin favoritos

    def test_solo_staff_puede_cambiar_permiso(self):
        url = f'/api/staff/clientes/{self.cliente.pk}/'
        self.assertEqual(self.api.put(url, {'puede_descargar_lista': True}, format='json').status_code, 403)
        admin = User.objects.create_user(username='admin', is_staff=True)
        self.api.force_authenticate(admin)
        self.assertEqual(self.api.put(url, {'puede_descargar_lista': True}, format='json').status_code, 200)
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.puede_descargar_lista)
        self.assertTrue(self.api.get(url).data['puede_descargar_lista'])
        self.assertEqual(self.api.put(url, {'puede_descargar_lista': False}, format='json').status_code, 200)
        self.cliente.refresh_from_db()
        self.assertFalse(self.cliente.puede_descargar_lista)


from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

class MigracionPermisoDescargaTests(TransactionTestCase):
    def test_clientes_anteriores_conservan_acceso(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('api', '0030_pedido_email_delivery_state')])
        apps = executor.loader.project_state([('api', '0030_pedido_email_delivery_state')]).apps
        user = apps.get_model('auth', 'User').objects.create(username='anterior')
        loc = apps.get_model('api', 'Localidades').objects.create(codigo='9998', nombre='Prueba')
        pago = apps.get_model('api', 'FormaPago').objects.create(id='98', nombre='Contado', descuento=0, punitorio=0)
        old = apps.get_model('api', 'Cliente').objects.create(user=user, numero_cliente='99998', nombre='Anterior', lista_precio='1', codigo_localidad=loc, condicion_pago=pago, tipo_responsable_iva='C')
        executor = MigrationExecutor(connection)
        executor.migrate([('api', '0031_cliente_puede_descargar_lista')])
        apps = executor.loader.project_state([('api', '0031_cliente_puede_descargar_lista')]).apps
        self.assertTrue(apps.get_model('api', 'Cliente').objects.get(pk=old.pk).puede_descargar_lista)

