from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('matcher.urls')),  # Include matcher URLs at root
]

# In settings.py, keep:
