from django.contrib import admin
from django.urls import path, include

admin.site.site_header = "RSS Pipeline Admin"
admin.site.site_title = "RSS Pipeline"
admin.site.index_title = "Dashboard"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
]
