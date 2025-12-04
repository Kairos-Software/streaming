from django.shortcuts import render


def home(request):
    cameras = {
        1: "http://192.168.0.186:8080/hls/cam1.m3u8",
        2: "http://192.168.0.186:8080/hls/cam2.m3u8",
        3: "http://192.168.0.186:8080/hls/cam3.m3u8",
    }
    return render(request, "core/home.html", {"cameras": cameras})
