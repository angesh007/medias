"""
dashboard/models.py

Django models that map 1-to-1 to your Supabase Postgres tables.
Django Admin reads from these via DATABASE_URL (same Supabase Postgres DB
that main.py writes to) — one source of truth, no duplication.

All models use managed=False so Django never tries to create/alter the tables
(you already created them via your SQL script in Supabase).
managed=False also means migrations only track the Python model definition,
not the actual DB schema.
"""

from django.db import models


# ══════════════════════════════════════════════════════════════
#  pipeline_runs
# ══════════════════════════════════════════════════════════════

class PipelineRun(models.Model):
    id              = models.UUIDField(primary_key=True)
    created_at      = models.DateTimeField()
    started_at      = models.DateTimeField(null=True, blank=True)
    finished_at     = models.DateTimeField(null=True, blank=True)
    status          = models.CharField(max_length=20)
    current_step    = models.IntegerField(default=0)
    step1_articles  = models.IntegerField(default=0)
    step2_detections = models.IntegerField(default=0)
    step3_reports   = models.IntegerField(default=0)
    failed_step     = models.IntegerField(null=True, blank=True)
    error_message   = models.TextField(blank=True, null=True)
    config_snapshot = models.JSONField(null=True, blank=True)
    storage_prefix  = models.TextField(blank=True, null=True)

    class Meta:
        managed     = False          # table already exists in Supabase
        db_table    = "pipeline_runs"
        ordering    = ["-created_at"]
        verbose_name = "Pipeline Run"
        verbose_name_plural = "Pipeline Runs"

    def __str__(self):
        ts = self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "?"
        return f"Run {str(self.id)[:8]} | {ts} | {self.status}"

    @property
    def duration_seconds(self):
        if self.started_at and self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds())
        return None


# ══════════════════════════════════════════════════════════════
#  pipeline_logs
# ══════════════════════════════════════════════════════════════

class PipelineLog(models.Model):
    id         = models.BigAutoField(primary_key=True)
    run        = models.ForeignKey(PipelineRun, on_delete=models.CASCADE,
                                   db_column="run_id", related_name="logs")
    created_at = models.DateTimeField()
    level      = models.CharField(max_length=20)
    step       = models.IntegerField(null=True, blank=True)
    message    = models.TextField()

    class Meta:
        managed  = False
        db_table = "pipeline_logs"
        ordering = ["created_at"]
        verbose_name = "Log Entry"
        verbose_name_plural = "Log Entries"

    def __str__(self):
        return f"[{self.level.upper()}] {self.message[:80]}"


# ══════════════════════════════════════════════════════════════
#  scraped_articles
# ══════════════════════════════════════════════════════════════

class ScrapedArticle(models.Model):
    id             = models.UUIDField(primary_key=True)
    run            = models.ForeignKey(PipelineRun, on_delete=models.CASCADE,
                                       db_column="run_id", related_name="articles")
    created_at     = models.DateTimeField()
    title          = models.TextField(blank=True, null=True)
    url            = models.TextField()
    site           = models.TextField(blank=True, null=True)
    published_date = models.TextField(blank=True, null=True)
    snippet        = models.TextField(blank=True, null=True)
    search_term    = models.TextField(blank=True, null=True)
    date_range     = models.TextField(blank=True, null=True)
    country        = models.TextField(blank=True, null=True)
    scrape_status  = models.TextField(blank=True, null=True)
    scrape_method  = models.TextField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    content        = models.TextField(blank=True, null=True)
    storage_path   = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = "scraped_articles"
        ordering = ["-created_at"]
        verbose_name = "Scraped Article"
        verbose_name_plural = "Scraped Articles"

    def __str__(self):
        return f"{self.site} — {(self.title or '')[:60]}"


# ══════════════════════════════════════════════════════════════
#  detections
# ══════════════════════════════════════════════════════════════

class Detection(models.Model):
    id                = models.UUIDField(primary_key=True)
    run               = models.ForeignKey(PipelineRun, on_delete=models.CASCADE,
                                          db_column="run_id", related_name="detections")
    article           = models.ForeignKey(ScrapedArticle, on_delete=models.SET_NULL,
                                          null=True, blank=True, db_column="article_id",
                                          related_name="detections")
    created_at        = models.DateTimeField()
    url               = models.TextField(blank=True, null=True)
    title             = models.TextField(blank=True, null=True)
    site              = models.TextField(blank=True, null=True)
    published_date    = models.TextField(blank=True, null=True)
    status            = models.TextField(blank=True, null=True)
    skip_reason       = models.TextField(blank=True, null=True)
    total_detections  = models.IntegerField(default=0)
    strong_phobic     = models.IntegerField(default=0)
    medium_phobic     = models.IntegerField(default=0)
    weak_phobic       = models.IntegerField(default=0)
    authors           = models.JSONField(null=True, blank=True)
    detection_payload = models.JSONField(null=True, blank=True)
    storage_path      = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = "detections"
        ordering = ["-created_at"]
        verbose_name = "Detection"
        verbose_name_plural = "Detections"

    def __str__(self):
        return f"{self.site} — {(self.title or '')[:60]} [{self.total_detections} hits]"


# ══════════════════════════════════════════════════════════════
#  reports
# ══════════════════════════════════════════════════════════════

class Report(models.Model):
    id                  = models.UUIDField(primary_key=True)
    run                 = models.ForeignKey(PipelineRun, on_delete=models.CASCADE,
                                            db_column="run_id", related_name="reports")
    detection           = models.ForeignKey(Detection, on_delete=models.SET_NULL,
                                            null=True, blank=True,
                                            db_column="detection_id",
                                            related_name="reports")
    created_at          = models.DateTimeField()
    url                 = models.TextField(blank=True, null=True)
    title               = models.TextField(blank=True, null=True)
    site                = models.TextField(blank=True, null=True)
    authors             = models.JSONField(null=True, blank=True)
    final_score         = models.FloatField(null=True, blank=True)
    executive_summary   = models.TextField(blank=True, null=True)
    qualitative_insight = models.TextField(blank=True, null=True)
    refs_count          = models.IntegerField(default=0)
    report_payload      = models.JSONField(null=True, blank=True)
    storage_path        = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = "reports"
        ordering = ["-created_at"]
        verbose_name = "Report"
        verbose_name_plural = "Reports"

    def __str__(self):
        score = f"{self.final_score:.1f}" if self.final_score else "?"
        return f"{self.site} — {(self.title or '')[:50]} [score={score}]"


# ══════════════════════════════════════════════════════════════
#  pipeline_config
# ══════════════════════════════════════════════════════════════

class PipelineConfig(models.Model):
    id          = models.BigAutoField(primary_key=True)
    created_at  = models.DateTimeField()
    updated_at  = models.DateTimeField()
    key         = models.TextField(unique=True)
    value       = models.JSONField()
    description = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = "pipeline_config"
        ordering = ["key"]
        verbose_name = "Config"
        verbose_name_plural = "Pipeline Config"

    def __str__(self):
        return f"{self.key}"


# ══════════════════════════════════════════════════════════════
#  internal_documents
# ══════════════════════════════════════════════════════════════

class InternalDocument(models.Model):
    id           = models.BigAutoField(primary_key=True)
    uploaded_at  = models.DateTimeField()
    storage_path = models.TextField()
    bucket       = models.TextField()
    filename     = models.TextField()
    size_bytes   = models.BigIntegerField(null=True, blank=True)
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True, null=True)

    class Meta:
        managed  = False
        db_table = "internal_documents"
        ordering = ["-uploaded_at"]
        verbose_name = "Internal Document"
        verbose_name_plural = "Internal Documents"

    def __str__(self):
        return f"{self.filename} ({'active' if self.is_active else 'inactive'})"
