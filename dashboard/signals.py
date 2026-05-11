"""
dashboard/signals.py

When PipelineConfig is saved via the admin (e.g. sites or date_ranges updated),
auto-enqueue a new pipeline run via the Supabase pending_runs queue.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PipelineConfig


@receiver(post_save, sender=PipelineConfig)
def config_saved(sender, instance, **kwargs):
    # Only queue for keys that affect scraping behaviour
    trigger_keys = {"sites", "date_ranges", "search_terms"}
    if instance.key in trigger_keys:
        try:
            from pipeline.db import enqueue_pending
            enqueue_pending(triggered_by=f"config_save:{instance.key}")
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Could not enqueue pending run after config save: %s", exc
            )
