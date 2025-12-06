from django.shortcuts import render

def home(request):
    # Base URL usando tu subdominio con HTTPS (recomendado si configuraste SSL en NGINX)
    base_url = "https://camaras.grupokairosarg.com/live/hls"

    # Diccionario de cámaras disponibles
    cameras = {
        1: f"{base_url}/cam1/index.m3u8",
        2: f"{base_url}/cam2/index.m3u8",
        3: f"{base_url}/cam3/index.m3u8",
    }

    # Renderiza el template con las URLs de las cámaras
    return render(request, "core/home.html", {"cameras": cameras})
