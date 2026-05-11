"""dashboard/views.py — lightweight status redirect (admin is the main UI)"""
from django.shortcuts import redirect

def index(request):
    return redirect("/admin/")
