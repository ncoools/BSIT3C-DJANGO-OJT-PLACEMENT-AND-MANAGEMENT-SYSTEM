from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='dashboard'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/time-in/', views.student_time_in, name='student_time_in'),
    path('student/time-out/', views.student_time_out, name='student_time_out'),
    path('supervisor-dashboard/', views.supervisor_dashboard, name='supervisor_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('change-password/', views.password_change_view, name='password_change'),
    path('supervisor-register/', views.supervisor_register_view, name='supervisor_register'),
    path('approvals/', views.approvals_view, name='approvals'),
    path('approvals/<int:user_id>/approve/', views.approve_supervisor, name='approve_supervisor'),
    path('approvals/<int:user_id>/reject/', views.reject_supervisor, name='reject_supervisor'),
    path('accounts/', views.accounts_view, name='accounts'),
    path('accounts/<int:user_id>/action/', views.account_action, name='account_action'),
]