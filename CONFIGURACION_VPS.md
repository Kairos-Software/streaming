# 🔧 Configuración para VPS Ubuntu

## 📋 Resumen de Cambios Realizados

Se han modificado los archivos para que las URLs y puertos sean configurables mediante variables de entorno, **sin cambiar la lógica del código**. Todo funciona igual que antes localmente, y solo necesitas cambiar las variables de entorno en la VPS.

## ✅ Archivos Modificados

1. **`streaming/settings.py`** - Agregadas variables de configuración
2. **`core/views.py`** - Usa `settings.HLS_BASE_URL` y `settings.RTMP_PUBLIC_URL`
3. **`core/services/estado_transmision.py`** - Usa `settings.HLS_BASE_URL`
4. **`core/services/notificaciones_tiempo_real.py`** - Usa `settings.HLS_BASE_URL`
5. **`core/services/ffmpeg_manager.py`** - Usa `settings.RTMP_INTERNAL_HOST/PORT` y detecta FFmpeg en Linux

## 🚀 Configuración para Producción en VPS

### Opción 1: Variables de Entorno (Recomendado)

En la VPS, antes de ejecutar Django, configura estas variables de entorno:

```bash
export HLS_BASE_URL="https://kaircampanel.grupokairosarg.com:9443"
export RTMP_PUBLIC_URL="rtmp://kaircampanel.grupokairosarg.com:9000/live"
export RTMP_INTERNAL_HOST="127.0.0.1"
export RTMP_INTERNAL_PORT="9000"
export FFMPEG_BIN="/usr/bin/ffmpeg"  # Opcional, se detecta automáticamente
```

O si usas HTTPS:
```bash
export HLS_BASE_URL="https://kaircampanel.grupokairosarg.com:9443"
```

O si prefieres HTTP:
```bash
export HLS_BASE_URL="http://kaircampanel.grupokairosarg.com:9080"
```

### Opción 2: Modificar settings.py Directamente

Si prefieres no usar variables de entorno, puedes modificar directamente en `streaming/settings.py` las líneas al final del archivo:

```python
# Cambiar estas líneas en settings.py:
HLS_BASE_URL = 'https://kaircampanel.grupokairosarg.com:9443'  # o http://...:9080
RTMP_PUBLIC_URL = 'rtmp://kaircampanel.grupokairosarg.com:9000/live'
RTMP_INTERNAL_HOST = '127.0.0.1'  # Siempre localhost (interno)
RTMP_INTERNAL_PORT = '9000'  # Puerto RTMP interno
```

## 📝 Valores por Defecto (Desarrollo Local)

Si **NO** configuras las variables de entorno, el sistema usará estos valores por defecto (funciona localmente):

- `HLS_BASE_URL = 'http://localhost:8080'`
- `RTMP_PUBLIC_URL = 'rtmp://127.0.0.1:1935/live'`
- `RTMP_INTERNAL_HOST = '127.0.0.1'`
- `RTMP_INTERNAL_PORT = '9000'`

## 🔍 Dónde se Usan Estas Configuraciones

### HLS_BASE_URL
- **`core/views.py`** línea ~299: URLs de streams individuales de cámaras
- **`core/services/estado_transmision.py`** línea ~89: URL del stream del programa completo
- **`core/services/notificaciones_tiempo_real.py`** líneas ~21 y ~51: URLs en notificaciones WebSocket

### RTMP_PUBLIC_URL
- **`core/views.py`** línea ~510: URL que se muestra al usuario para conectar OBS

### RTMP_INTERNAL_HOST/PORT
- **`core/services/ffmpeg_manager.py`** líneas ~31-32: URLs internas para FFmpeg (siempre localhost)

## 🎯 Configuración Específica para tu VPS

Según tus especificaciones:
- **Subdominio:** `kaircampanel.grupokairosarg.com`
- **HLS HTTP:** puerto `9080`
- **HLS HTTPS:** puerto `9443`
- **RTMP:** puerto `9000`
- **IP VPS:** `85.209.92.238`

### Configuración Recomendada (HTTPS):

```bash
export HLS_BASE_URL="https://kaircampanel.grupokairosarg.com:9443"
export RTMP_PUBLIC_URL="rtmp://kaircampanel.grupokairosarg.com:9000/live"
```

### O si prefieres HTTP:

```bash
export HLS_BASE_URL="http://kaircampanel.grupokairosarg.com:9080"
export RTMP_PUBLIC_URL="rtmp://kaircampanel.grupokairosarg.com:9000/live"
```

## ⚙️ Configuración en systemd (si usas servicio)

Si ejecutas Django con systemd, agrega las variables en el archivo de servicio:

```ini
[Service]
Environment="HLS_BASE_URL=https://kaircampanel.grupokairosarg.com:9443"
Environment="RTMP_PUBLIC_URL=rtmp://kaircampanel.grupokairosarg.com:9000/live"
Environment="RTMP_INTERNAL_HOST=127.0.0.1"
Environment="RTMP_INTERNAL_PORT=9000"
```

## ✅ Verificación

Después de configurar, verifica que:

1. Los streams HLS se cargan correctamente en el navegador
2. La URL RTMP que se muestra al usuario es la correcta
3. FFmpeg puede conectarse al RTMP interno (localhost:9000)
4. Los WebSockets funcionan correctamente

## 🔄 Sin Cambios en la Lógica

**Importante:** Estos cambios **NO modifican la lógica** del código. Solo hacen que las URLs sean configurables. Todo funciona exactamente igual que antes, solo cambias dónde apuntan las URLs.
