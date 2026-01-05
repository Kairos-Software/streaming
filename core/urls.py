# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # =========================
    # Autenticación
    # =========================
    path("login/", views.login_view, name="login"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),

    # =========================
    # CRUD usuarios (admin)
    # =========================
    path("crear-usuario/", views.crear_usuario, name="crear_usuario"),
    path("usuarios/", views.ver_usuarios, name="ver_usuarios"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/eliminar/", views.eliminar_usuario, name="eliminar_usuario"),

    # =========================
    # Streaming / cámaras
    # =========================
    path(
        "autorizar-camara/<int:cam_index>/",
        views.autorizar_camara,
        name="autorizar_camara"
    ),
    path(
        "rechazar-camara/<int:cam_index>/",
        views.rechazar_camara,
        name="rechazar_camara"
    ),
    path(
        "cerrar-camara/<int:cam_index>/",
        views.cerrar_camara,
        name="cerrar_camara"
    ),
    path(
        "poner-al-aire/<int:cam_index>/",
        views.poner_al_aire,
        name="poner_al_aire"
    ),
    path(
        "estado-camaras/",
        views.estado_camaras,
        name="estado_camaras"
    ),

    # =========================
    # Audio
    # =========================
    path("audio/", views.audio, name="audio"),

    # =========================
    # RTMP callbacks (nginx)
    # =========================
    path(
        "validar-publicacion/",
        views.validar_publicacion_stream_rtmp,
        name="validar_publicacion_stream_rtmp"
    ),
    path(
        "stream-finalizado/",
        views.stream_finalizado,
        name="stream_finalizado"
    ),
    path(
        "detener-transmision/",
        views.detener_transmision,
        name="detener_transmision"
    ),

    # =========================
    # PIN
    # =========================
    path("pin/gestion/", views.gestionar_pin, name="gestionar_pin"),

    # =========================
    # Otros
    # =========================
    path("tutorial/", views.tutorial, name="tutorial"),
]
