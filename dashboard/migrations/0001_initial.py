"""
Initial migration — all models are managed=False (tables already exist in Supabase).
This migration only registers the models with Django's migration framework so
that django.contrib.admin, auth, sessions, etc. work correctly.
No CREATE TABLE statements are emitted.
"""
from django.db import migrations


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        # No operations needed — tables are pre-created by your Supabase SQL script.
        # managed=False models don't need Django to create/alter their tables.
    ]
