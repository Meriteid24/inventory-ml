from django.urls import path
from . import views
from .views import get_inventory_data#

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('about/', views.AboutView.as_view(), name='about'),
    path('api/inventory-data/', get_inventory_data, name='inventory-data'),
    path('logout/', views.logout_view, name='logout'),
]
