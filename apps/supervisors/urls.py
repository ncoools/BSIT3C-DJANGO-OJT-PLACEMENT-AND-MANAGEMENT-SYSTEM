from django.urls import path

from . import views

app_name = 'supervisors'

urlpatterns = [
    path('', views.supervisor_list, name='list'),
    path('add/', views.supervisor_create, name='create'),
    path('<int:pk>/edit/', views.supervisor_update, name='update'),
    path('<int:pk>/delete/', views.supervisor_delete, name='delete'),
]
