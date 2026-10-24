from django.urls import path

from . import views

app_name = 'placements'

urlpatterns = [
    path('', views.placement_list, name='list'),
    path('add/', views.placement_create, name='create'),
    path('<int:pk>/edit/', views.placement_update, name='update'),
    path('<int:pk>/delete/', views.placement_delete, name='delete'),
]
