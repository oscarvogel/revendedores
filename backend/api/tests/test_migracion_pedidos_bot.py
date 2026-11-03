from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ReconciliacionMigracionesBotTests(TransactionTestCase):
    def test_conserva_la_tabla_y_los_datos_historicos(self):
        executor = MigrationExecutor(connection)
        before = ('api', '0032_merge_permiso_produccion')
        executor.migrate([before])
        apps = executor.loader.project_state([before]).apps
        conversation = apps.get_model('api', 'BotConversation')
        conversation.objects.create(session_id='ensayo-migracion', origen='api')

        executor = MigrationExecutor(connection)
        executor.migrate([('api', '0033_merge_pedidos_y_bot')])
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM api_botconversation WHERE session_id = %s", ['ensayo-migracion'])
            self.assertEqual(cursor.fetchone()[0], 1)
            cursor.execute('SELECT conversation_id FROM api_botconversationlog LIMIT 1')

        latest_apps = executor.loader.project_state([('api', '0033_merge_pedidos_y_bot')]).apps
        self.assertIsNotNone(latest_apps.get_model('api', 'BotConversation'))
        self.assertIsNotNone(latest_apps.get_model('api', 'BotConversationLog')._meta.get_field('conversation'))
        from django.contrib.auth.models import User
        from api.models import BotConversation
        user = User.objects.create_user(username='migracion-bot')
        saved = BotConversation.objects.get(session_id='ensayo-migracion')
        saved.usuario = user
        saved.save(update_fields=['usuario'])
        user.delete()
        saved.refresh_from_db()
        self.assertIsNone(saved.usuario)
