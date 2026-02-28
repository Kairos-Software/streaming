from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import views_radio  # ← agregar este import
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # --- AUTENTICACIÓN Y HOME ---
    path("login/", views.login_view, name="login"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),
    
    # --- RECUPERACIÓN DE CONTRASEÑA ---
    path('reset/password_reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        html_email_template_name='registration/password_reset_email.html',
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

    # --- STREAMING ---
    path("validar-publicacion/", views.validar_publicacion, name="validar_publicacion"),
    path("stream-finalizado/", views.stream_finalizado, name="stream_finalizado"),
    path("estado-camaras/", views.estado_camaras, name="estado_camaras"),
    path("autorizar-camara/<int:cam_index>/", views.autorizar_camara, name="autorizar_camara"),
    path("rechazar-camara/<int:cam_index>/", views.rechazar_camara, name="rechazar_camara"),
    path("poner-al-aire/<int:cam_index>/", views.poner_al_aire, name="poner_al_aire"),
    path("detener-transmision/", views.detener_transmision, name="detener_transmision"),
    path("cerrar-camara/<int:cam_index>/", views.cerrar_camara, name="cerrar_camara"),

    # --- EXTRAS ---
    path("audio/", views.audio, name="audio"),
    path("tutorial/", views.tutorial, name="tutorial"),
    path("autorizar-program-switch/", views.autorizar_program_switch),

    # --- MODO RADIO ---
    path("radio/activar/",          views_radio.activar_modo_radio,    name="activar_modo_radio"),
    path("radio/desactivar/",       views_radio.desactivar_modo_radio,  name="desactivar_modo_radio"),
    path("radio/estado/",           views_radio.estado_modo_radio,      name="estado_modo_radio"),
    path("radio/imagen/subir/",     views_radio.subir_imagen_radio,     name="subir_imagen_radio"),
    path("radio/imagen/eliminar/",  views_radio.eliminar_imagen_radio,  name="eliminar_imagen_radio"),
    path("radio/imagen/estado/",    views_radio.estado_imagen_radio,    name="estado_imagen_radio"),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)