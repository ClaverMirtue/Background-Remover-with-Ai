from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='removerapp/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('download-image/<int:image_id>/', views.download_image, name='download_image'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
] 