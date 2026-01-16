from django.urls import path
from django.contrib.auth import views as auth_views  # <--- Importante para el cambio de contraseña
from . import views

urlpatterns = [
    # --- AUTENTICACIÓN Y HOME ---
    path("login/", views.login_view, name="login"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),
    
    # --- RECUPERACIÓN DE CONTRASEÑA (NUEVO) ---
    path('reset/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        html_email_template_name='registration/password_reset_email.html',  # <--- Para que el email sea HTML bonito
    ), name='password_reset'),
    
    path('reset/password_reset_done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),

    # --- AJUSTES DE USUARIO ---
    path('ajustes/perfil/', views.ajustes_perfil, name='ajustes_perfil'),
    path('ajustes/seguridad/', views.ajustes_seguridad, name='ajustes_seguridad'),
    path('ajustes/seguridad/desactivar/', views.desactivar_2fa, name='desactivar_2fa'),
    path('ajustes/preferencias/', views.ajustes_preferencias, name='ajustes_preferencias'),
    path('ajustes/notificaciones/', views.ajustes_notificaciones, name='ajustes_notificaciones'),
    path('ajustes/conexiones/', views.ajustes_conexiones, name='ajustes_conexiones'),

    # --- SEGURIDAD 2FA ---
    path('seguridad/2fa/', views.configurar_2fa, name='configurar_2fa'),

    # --- PIN ---
    path("pin/gestion/", views.gestionar_pin, name="gestionar_pin"),

    # --- CRUD USUARIOS (Solo Admin) ---
    path("crear-usuario/", views.crear_usuario, name="crear_usuario"),
    path("usuarios/", views.ver_usuarios, name="ver_usuarios"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/eliminar/", views.eliminar_usuario, name="eliminar_usuario"),

    # --- STREAMING (SISTEMA DE SEGURIDAD CON PIN) ---
    # 1. Comunicación con Nginx (Automática)
    path("validar-publicacion/", views.validar_publicacion, name="validar_publicacion"),
    path("stream-finalizado/", views.stream_finalizado, name="stream_finalizado"),

    # 2. Gestión desde la Web (Frontend y PIN)
    path("estado-camaras/", views.estado_camaras, name="estado_camaras"),
    path("autorizar-camara/<int:cam_index>/", views.autorizar_camara, name="autorizar_camara"),
    path("rechazar-camara/<int:cam_index>/", views.rechazar_camara, name="rechazar_camara"),
    
    # --- RUTAS NUEVAS PARA FFMPEG ---
    path("poner-al-aire/<int:cam_index>/", views.poner_al_aire, name="poner_al_aire"),
    path("detener-transmision/", views.detener_transmision, name="detener_transmision"),
    path("cerrar-camara/<int:cam_index>/", views.cerrar_camara, name="cerrar_camara"),

    # --- EXTRAS ---
    path("audio/", views.audio, name="audio"),
    path("tutorial/", views.tutorial, name="tutorial"),
    path("autorizar-program-switch/", views.autorizar_program_switch),
]