from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"

    def ready(self):
        # Connect post_save signal so saving a SiteConfig or DateRangeConfig
        # automatically queues a new pipeline run.
        from . import signals  # noqa: F401
