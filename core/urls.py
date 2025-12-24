# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("", views.home, name="home"),
    path("logout/", views.logout_view, name="logout"),

    # CRUD usuarios
    path("crear-usuario/", views.crear_usuario, name="crear_usuario"),
    path("usuarios/", views.ver_usuarios, name="ver_usuarios"),
    path("usuarios/<int:pk>/editar/", views.editar_usuario, name="editar_usuario"),
    path("usuarios/<int:pk>/eliminar/", views.eliminar_usuario, name="eliminar_usuario"),

    # Streaming
    path("autorizar-camara/<int:cam_index>/", views.autorizar_camara, name="autorizar_camara"),

    # RTMP callbacks
    path("validar-publicacion/", views.validar_publicacion_stream_rtmp, name="validar_publicacion_stream_rtmp"),
    path("stream-finalizado/", views.stream_finalizado, name="stream_finalizado"),

    # PIN
    path("pin/gestion/", views.gestionar_pin, name="gestionar_pin"),
    path(
    "rechazar-camara/<int:cam_index>/",
    views.rechazar_camara,
    name="rechazar_camara"
),

    path("estado-camaras/", views.estado_camaras, name="estado_camaras"),
    path("poner-al-aire/<int:cam_index>/", views.poner_al_aire, name="poner_al_aire"),
    path("audio/", views.audio, name="audio"),
    path("tutorial/", views.tutorial, name="tutorial"),


]
