from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        try:
            from library_system.mongo_signals import register_signals
            register_signals()
        except Exception:
            pass

