"""
dashboard/admin.py

Django Admin UI reading directly from Supabase Postgres via DATABASE_URL.
All models have managed=False so this is read-only from Django's perspective —
main.py does all the writing via supabase-py.

Panels:
  1. Pipeline Runs  — colour-coded status, auto-refresh, inline logs + articles
  2. Scraped Articles — search/filter by site, status
  3. Detections      — filter by site, step status, score range
  4. Reports         — filter by site, score; link to Storage JSON
  5. Pipeline Config — edit key/value pairs to control the next run
  6. Internal Documents — track which Internaldoc is active
"""

import subprocess
import sys

from django.contrib import admin, messages
from django.utils.html import format_html
from django_json_widget.widgets import JSONEditorWidget
from django.db import models as db_models

from .models import (
    Detection, InternalDocument, PipelineConfig,
    PipelineLog, PipelineRun, Report, ScrapedArticle,
)

# ── Auto-refresh JS injected into Run changelist ──────────────
AUTO_REFRESH_JS = """
<script>
(function() {
    var path = window.location.pathname;
    if (path.indexOf('/pipelinerun/') !== -1 && path.split('/').length <= 5) {
        setTimeout(function() { window.location.reload(); }, 10000);
        console.log('Auto-refresh in 10s');
    }
})();
</script>
"""

STATUS_COLOURS = {
    "complete": "#27ae60",
    "running":  "#f39c12",
    "started":  "#3498db",
    "failed":   "#e74c3c",
    "pending":  "#95a5a6",
}

STEP_LABELS = {0: "—", 1: "Scraping", 2: "Detecting", 3: "Reporting"}


# ══════════════════════════════════════════════════════════════
#  INLINES
# ══════════════════════════════════════════════════════════════

class PipelineLogInline(admin.TabularInline):
    model        = PipelineLog
    extra        = 0
    max_num      = 0
    can_delete   = False
    fields       = ["created_at", "level_badge", "step", "message_truncated"]
    readonly_fields = ["created_at", "level_badge", "step", "message_truncated"]
    ordering     = ["created_at"]
    verbose_name = "Log line"

    def level_badge(self, obj):
        colours = {"info": "#3498db", "warning": "#f39c12",
                   "error": "#e74c3c", "debug": "#95a5a6"}
        c = colours.get(obj.level, "#95a5a6")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 7px;'
            'border-radius:8px;font-size:11px">{}</span>', c, obj.level.upper()
        )
    level_badge.short_description = "Level"

    def message_truncated(self, obj):
        return (obj.message or "")[:120]
    message_truncated.short_description = "Message"


class ScrapedArticleInline(admin.TabularInline):
    model       = ScrapedArticle
    extra       = 0
    max_num     = 0
    can_delete  = False
    fields      = ["title_short", "site", "scrape_status", "scrape_method"]
    readonly_fields = ["title_short", "site", "scrape_status", "scrape_method"]
    show_change_link = True

    def title_short(self, obj):
        return (obj.title or "")[:70]
    title_short.short_description = "Title"


class DetectionInline(admin.TabularInline):
    model      = Detection
    extra      = 0
    max_num    = 0
    can_delete = False
    fields     = ["title_short", "site", "total_detections",
                  "strong_phobic", "medium_phobic", "weak_phobic", "status"]
    readonly_fields = ["title_short", "site", "total_detections",
                       "strong_phobic", "medium_phobic", "weak_phobic", "status"]
    show_change_link = True

    def title_short(self, obj):
        return (obj.title or "")[:60]
    title_short.short_description = "Title"


# ══════════════════════════════════════════════════════════════
#  PIPELINE RUN ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = [
        "short_id", "status_badge", "step_display",
        "created_at", "duration_display",
        "step1_articles", "step2_detections", "step3_reports",
        "error_preview",
    ]
    list_filter    = ["status"]
    search_fields  = ["id"]
    readonly_fields = [
        "id", "created_at", "started_at", "finished_at",
        "status", "current_step", "duration_display",
        "step1_articles", "step2_detections", "step3_reports",
        "failed_step", "error_message", "storage_prefix",
        "config_snapshot_pretty",
    ]
    formfield_overrides = {db_models.JSONField: {"widget": JSONEditorWidget}}
    inlines  = [PipelineLogInline, ScrapedArticleInline, DetectionInline]
    ordering = ["-created_at"]
    actions  = ["trigger_new_run"]

    def short_id(self, obj):
        return str(obj.id)[:8]
    short_id.short_description = "Run ID"

    def status_badge(self, obj):
        c = STATUS_COLOURS.get(obj.status, "#95a5a6")
        return format_html(
            '<span style="background:{};color:#fff;padding:3px 10px;'
            'border-radius:12px;font-size:12px;font-weight:600">{}</span>',
            c, obj.status.upper()
        )
    status_badge.short_description = "Status"

    def step_display(self, obj):
        label = STEP_LABELS.get(obj.current_step or 0, "?")
        return format_html('<span style="font-size:12px">Step {} — {}</span>',
                           obj.current_step or 0, label)
    step_display.short_description = "Current Step"

    def duration_display(self, obj):
        secs = obj.duration_seconds
        if secs is None:
            return "—"
        return f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
    duration_display.short_description = "Duration"

    def error_preview(self, obj):
        if obj.error_message:
            msg = f"Step {obj.failed_step}: {obj.error_message[:80]}…"
            return format_html(
                '<span style="color:#e74c3c" title="{}">{}</span>',
                obj.error_message, msg
            )
        return "—"
    error_preview.short_description = "Error"

    def config_snapshot_pretty(self, obj):
        import json
        if not obj.config_snapshot:
            return "—"
        return format_html("<pre style='font-size:12px'>{}</pre>",
                           json.dumps(obj.config_snapshot, indent=2))
    config_snapshot_pretty.short_description = "Config Snapshot"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["auto_refresh_js"] = AUTO_REFRESH_JS
        return super().changelist_view(request, extra_context)

    @admin.action(description="▶ Trigger a new pipeline run")
    def trigger_new_run(self, request, queryset):
        import threading
        try:
            from main import orchestrate
            t = threading.Thread(target=orchestrate, kwargs={"triggered_by": "admin_ui"}, daemon=True)
            t.start()
            self.message_user(request, "New pipeline run triggered!", messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Failed to trigger run: {exc}", messages.ERROR)
            
# ══════════════════════════════════════════════════════════════
#  SCRAPED ARTICLES ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(ScrapedArticle)
class ScrapedArticleAdmin(admin.ModelAdmin):
    list_display   = ["title_short", "site", "scrape_status",
                      "scrape_method", "published_date", "search_term"]
    list_filter    = ["site", "scrape_status", "scrape_method"]
    search_fields  = ["title", "url", "site"]
    readonly_fields = [
        "id", "run", "created_at", "title", "url", "site",
        "published_date", "snippet", "search_term", "date_range",
        "country", "scrape_status", "scrape_method",
        "failure_reason", "storage_path", "url_link",
    ]
    ordering = ["-created_at"]

    def title_short(self, obj):
        return (obj.title or "")[:70]
    title_short.short_description = "Title"

    def url_link(self, obj):
        if obj.url:
            return format_html('<a href="{}" target="_blank">Open ↗</a>', obj.url)
        return "—"
    url_link.short_description = "URL"


# ══════════════════════════════════════════════════════════════
#  DETECTIONS ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(Detection)
class DetectionAdmin(admin.ModelAdmin):
    list_display  = ["title_short", "site", "total_detections",
                     "strong_phobic", "medium_phobic", "weak_phobic",
                     "status", "storage_link"]
    list_filter   = ["site", "status"]
    search_fields = ["title", "url", "site"]
    readonly_fields = [
        "id", "run", "article", "created_at", "url", "title", "site",
        "published_date", "status", "skip_reason",
        "total_detections", "strong_phobic", "medium_phobic", "weak_phobic",
        "authors", "storage_path", "storage_link",
    ]
    formfield_overrides = {db_models.JSONField: {"widget": JSONEditorWidget}}
    ordering = ["-created_at"]

    def title_short(self, obj):
        return (obj.title or "")[:60]
    title_short.short_description = "Title"

    def storage_link(self, obj):
        if obj.storage_path:
            return format_html(
                '<a href="{}" target="_blank">Detection JSON ↗</a>', obj.storage_path
            )
        return "—"
    storage_link.short_description = "Storage"


# ══════════════════════════════════════════════════════════════
#  REPORTS ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display  = ["title_short", "site", "score_badge",
                     "refs_count", "authors_display", "storage_link"]
    list_filter   = ["site"]
    search_fields = ["title", "url", "site"]
    readonly_fields = [
        "id", "run", "detection", "created_at", "url", "title", "site",
        "authors", "final_score", "refs_count",
        "executive_summary", "qualitative_insight",
        "storage_path", "storage_link",
    ]
    formfield_overrides = {db_models.JSONField: {"widget": JSONEditorWidget}}
    ordering = ["-created_at"]

    def title_short(self, obj):
        return (obj.title or "")[:60]
    title_short.short_description = "Title"

    def score_badge(self, obj):
        if obj.final_score is None:
            return "—"
        try:
            score = float(obj.final_score)
        except (TypeError, ValueError):
            return "—"
        colour = "#27ae60" if score < 4 else "#f39c12" if score < 7 else "#e74c3c"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:8px;font-size:12px;font-weight:600">{}</span>',
            colour,
            f"{score:.1f}",
        )
    score_badge.short_description = "Score"   


    def authors_display(self, obj):
        authors = obj.authors or []
        return ", ".join(authors[:2]) + ("…" if len(authors) > 2 else "")
    authors_display.short_description = "Authors"

    def storage_link(self, obj):
        if obj.storage_path:
            return format_html(
                '<a href="{}" target="_blank">Report JSON ↗</a>', obj.storage_path
            )
        return "—"
    storage_link.short_description = "Report"


# ══════════════════════════════════════════════════════════════
#  PIPELINE CONFIG ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(PipelineConfig)
class PipelineConfigAdmin(admin.ModelAdmin):
    list_display  = ["key", "value_preview", "description", "updated_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["id", "created_at", "updated_at"]
    formfield_overrides = {db_models.JSONField: {"widget": JSONEditorWidget}}
    ordering = ["key"]

    def value_preview(self, obj):
        import json
        val = json.dumps(obj.value)
        return val[:80] + "…" if len(val) > 80 else val
    value_preview.short_description = "Value"


# ══════════════════════════════════════════════════════════════
#  INTERNAL DOCUMENTS ADMIN
# ══════════════════════════════════════════════════════════════

@admin.register(InternalDocument)
class InternalDocumentAdmin(admin.ModelAdmin):
    list_display  = ["filename", "is_active", "bucket",
                     "storage_path", "size_bytes", "uploaded_at"]
    list_filter   = ["is_active", "bucket"]
    readonly_fields = ["id", "uploaded_at"]
    ordering      = ["-uploaded_at"]
