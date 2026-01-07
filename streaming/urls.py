from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # --- SISTEMA DE RECUPERACIÓN (Con diseño Dark Mode) ---
    
    # 1. Pedir el Email
    path('reset_password/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             html_email_template_name='registration/password_reset_email.html' # <--- ESTO ARREGLA EL LINK
         ), 
         name='password_reset'),

    # 2. Mensaje "Correo Enviado"
    path('reset_password_sent/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),

    # 3. Ingresar Nueva Contraseña (Link del correo)
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),

    # 4. Éxito "Contraseña Cambiada"
    path('reset_password_complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    # --- RESTO DE LA APP ---
    path('', include('core.urls')),
]