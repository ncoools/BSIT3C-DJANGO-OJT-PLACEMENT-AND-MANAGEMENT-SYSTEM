from django.urls import path

from . import views

app_name = 'placements'

urlpatterns = [
    path('', views.placement_list, name='list'),
    path('add/', views.placement_create, name='create'),
    path('<int:pk>/edit/', views.placement_update, name='update'),
    path('<int:pk>/delete/', views.placement_delete, name='delete'),
    path('<int:pk>/requirements/', views.placement_requirement_list, name='requirement_list'),
    path('<int:pk>/requirements/add/', views.placement_requirement_create, name='requirement_create'),
    path('<int:pk>/requirements/<int:requirement_pk>/edit/', views.placement_requirement_update, name='requirement_update'),
    path('<int:pk>/requirements/<int:requirement_pk>/delete/', views.placement_requirement_delete, name='requirement_delete'),
    path('<int:pk>/evaluations/', views.placement_evaluation_list, name='evaluation_list'),
    path('<int:pk>/evaluations/add/', views.placement_evaluation_create, name='evaluation_create'),
    path('<int:pk>/evaluations/<int:evaluation_pk>/edit/', views.placement_evaluation_update, name='evaluation_update'),
    path('<int:pk>/evaluations/<int:evaluation_pk>/delete/', views.placement_evaluation_delete, name='evaluation_delete'),
    path('<int:pk>/reports/', views.placement_report_list, name='report_list'),
    path('<int:pk>/reports/add/', views.placement_report_create, name='report_create'),
    path('<int:pk>/reports/<int:report_pk>/edit/', views.placement_report_update, name='report_update'),
    path('<int:pk>/reports/<int:report_pk>/delete/', views.placement_report_delete, name='report_delete'),
]
