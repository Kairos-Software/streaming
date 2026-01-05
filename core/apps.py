from django.apps import AppConfig
from django.db.utils import OperationalError


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from .models import StreamConnection
            deleted, _ = StreamConnection.objects.all().delete()
            if deleted:
                print(f"🧹 Limpieza inicial: {deleted} streams eliminados")
        except OperationalError:
            # DB todavía no lista (migraciones, etc)
            pass
