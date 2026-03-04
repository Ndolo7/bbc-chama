from django.urls import path
from . import views

app_name = 'chama'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('contributions/', views.contributions, name='contributions'),
    path('contributions/add/', views.add_contribution, name='add_contribution'),
    path('contributions/parse/', views.parse_sms, name='parse_sms'),
    path('contributions/<int:pk>/delete/', views.delete_contribution, name='delete_contribution'),
    path('members/<int:pk>/', views.member_detail, name='member_detail'),
    path('reports/', views.reports, name='reports'),
    path('reports/all/', views.reports_all, name='reports_all'),
]
