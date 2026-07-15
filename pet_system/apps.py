from django.apps import AppConfig


class PetSystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pet_system'

    def ready(self):
        pass
