from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from chama import views as chama_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='chama/login.html'), name='login'),
    path('demo/', chama_views.demo_login, name='demo_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('chama.urls')),
]
