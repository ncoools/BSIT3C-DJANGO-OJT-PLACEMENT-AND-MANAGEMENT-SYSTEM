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
    path('supervisor-register/', views.supervisor_register_view, name='supervisor_register'),
]