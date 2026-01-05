# Guía paso a paso (explicativa) para fijar un “master” de audio en una transmisión multicámara desde tu app web

# 1) Objetivo
# - Mantener un audio “master” constante (micrófono, interfaz, mixer o ManyCam) mientras el video puede cambiar de cámara.
# - Resolverlo desde el navegador con APIs web (MediaDevices/WebRTC), usando Django como backend de control, no de captura.

# 2) Arquitectura mínima
# - Frontend (navegador): captura de dispositivos, selección de fuente, combinación audio+video, envío del stream.
# - Backend (Django): autenticación, permisos, señalización (WebSockets/Channels), y distribución/gestión del stream.
# - Servidor de media opcional (SFU/MCU): Janus, mediasoup, Jitsi, o RTMP/HLS si el flujo es unidireccional/broadcast.

# 3) Cómo detecta el navegador las fuentes de audio
# - Todo lo que conectes a la PC y el sistema operativo reconozca como “dispositivo de entrada” aparecerá en el navegador.
#   Ejemplos: micrófonos USB, interfaces (Focusrite, Behringer), mixers con salida USB, fuentes virtuales (ManyCam).
# - La API: navigator.mediaDevices.enumerateDevices() lista ‘audioinput’ y ‘videoinput’.
# - Nota: por privacidad, las etiquetas (nombres) de los dispositivos suelen estar vacías hasta que el usuario otorga permiso.

# 4) Flujo de selección de audio “master” (frontend)
# - Paso 1: Solicitar permiso para audio (getUserMedia({ audio: true })).
# - Paso 2: Enumerar dispositivos y renderizar un selector de ‘audioinput’ (micrófono/interfaz/mixer/ManyCam).
# - Paso 3: Cuando el usuario elige uno, pedir getUserMedia({ audio: { deviceId: ‘elegido’ } }) para fijar el master.
# - Paso 4: Guardar ese MediaStreamTrack de audio como tu “master” y no reemplazarlo al cambiar de cámara.

# 5) Captura de video separada (multicámara)
# - Pedir video sin audio: getUserMedia({ video: true, audio: false }) o usar MediaStreamTrack de cámaras específicas.
# - Para cambiar de cámara, solicitas un nuevo track de video y reemplazas SOLO el track de video en el stream combinado.
# - El track de audio master se mantiene intacto.

# 6) Combinar audio master + video actual
# - Crear un MediaStream combinando el track de audio master y el track de video seleccionado.
# - Ejemplo conceptual: new MediaStream([videoTrackActual, audioMasterTrack]).
# - Ese stream combinado es el que se muestra en el reproductor local y se envía por WebRTC.

# 7) Configuración de calidad del audio
# - Al pedir el audio, especifica restricciones para calidad “pro”:
#   sampleRate=48000, channelCount=2, echoCancellation=false, noiseSuppression=false, autoGainControl=false.
# - Esto evita procesos del navegador que alteran la señal (útil en música/conciertos).
# - Ten presente que el dispositivo debe soportar los parámetros; algunos navegadores ajustarán al valor más cercano.

# 8) ManyCam y fuentes virtuales
# - Si ManyCam expone una fuente de audio/video virtual, aparecerá como dispositivo ‘audioinput’/‘videoinput’.
# - Puedes usar ManyCam solo para video y fijar como master un micrófono/interfaz/mixer, o viceversa.

# 9) Envío del stream (WebRTC)
# - Crear RTCPeerConnection, añadir tracks del stream combinado (addTrack).
# - Señalización (ofertas/respuestas ICE) via Django Channels/WebSockets.
# - El servidor SFU puede recibir múltiples contribuciones y retransmitir (si necesitas escalar a muchos espectadores en tiempo real).
# - Para broadcast unidireccional, evalúa generar una salida RTMP desde el navegador (vía gateway) o enviar a un “ingest” con OBS/ffmpeg.

# 10) Django como backend de control
# - No accede al hardware del usuario; el navegador captura.
# - Django gestiona login, permisos (solo usuarios autorizados pueden transmitir), y la señalización WebRTC.
# - Mantén un modelo de “sesión de transmisión” que registre: fuente de audio elegida, cámara actual, estado, y métricas.

# 11) UX para el selector de audio master
# - Un menú desplegable de “Fuente de audio” con lista de dispositivos (nombre + deviceId).
# - Botón “Fijar como master” que crea/reemplaza el track master en el stream.
# - Indicador de nivel (meter) para validar señal (AudioWorklet/AnalyserNode).
# - Mensajes claros si el dispositivo se desconecta o cambia.

# 12) Cambiar de cámara sin tocar el audio
# - Al seleccionar una nueva cámara, obtén su video track y usa RTCRtpSender.replaceTrack() (WebRTC) o recrea el MediaStream solo con video.
# - No llames getUserMedia de audio de la nueva cámara: el audio master permanece.

# 13) Consideraciones de permisos y HTTPS
# - getUserMedia requiere contexto seguro (HTTPS) y permiso del usuario.
# - Algunas políticas de autoplay bloquean reproducción sin interacción; usa “click para iniciar” antes de reproducir el preview.
# - En iOS/Safari, HLS puede ser preferible para consumo; WebRTC funciona pero tiene particularidades (latencia y compatibilidad).

# 14) Estabilidad y reconexión de dispositivos
# - Si el dispositivo master se desconecta, escucha eventos y ofrece reconectar o seleccionar otro.
# - Persistir la elección del usuario (localStorage) y reintentar con el deviceId anterior si sigue disponible.
# - Mostrar estados: “capturando”, “sin señal”, “reconectando”.

# 15) Parámetros de codificación
# - El navegador codifica audio (Opus) en WebRTC con buena calidad para voz y música.
# - En eventos musicales, desactivar supresiones y AGC mejora fidelidad; ajustar el bitrate si tu SFU/MCU lo permite.
# - Si haces ingest a RTMP, ffmpeg/OBS controlan codec (AAC generalmente) y bitrate.

# 16) Diagnóstico y medición
# - Usa getStats() de RTCPeerConnection para revisar bitrate, jitter, pérdida de paquetes.
# - AnalyserNode para visualizar niveles y verificar clipping (evita saturación desde la fuente física).
# - Logea cambios de dispositivos y errores de permisos para soporte técnico.

# 17) Seguridad y control de acceso
# - Usuarios deben autenticarse en Django; solo roles con permiso pueden iniciar transmisión.
# - Tokens temporales para la sesión de WebRTC (validados en el backend).
# - Auditoría: registra inicio/fin, fuentes seleccionadas, y métricas de calidad.

# 18) Escalabilidad y distribución
# - Para pocos espectadores: P2P o un SFU pequeño (mediasoup/Janus).
# - Para muchos: SFU en cluster + CDN para HLS si aceptas mayor latencia.
# - Django orquesta y provee las URLs/credenciales; el media server maneja la carga.

# 19) Buenas prácticas de audio
# - Usar interfaz/mixer de calidad, ajustar ganancia física, y monitorear con auriculares.
# - Evitar efectos de sistema (enhancements) y asegurar sample rate consistente (48 kHz ideal para video).
# - Prueba previa: playlists de referencia y voz para balancear antes del evento.

# 20) Mensaje clave
# - Sí: el navegador reconoce micrófonos, interfaces y mixers como ‘audioinput’.
# - Tu app fija uno como “master” y lo mantiene constante, combinándolo con cualquier cámara.
# - Django habilita la experiencia (permisos, señalización, acceso), pero la captura y la mezcla lógica se hacen en el navegador.


#==========================================================================================================================================

# --- Detalles adicionales a considerar ---

# Drivers y compatibilidad del sistema operativo
# - El navegador solo reconoce dispositivos que el sistema operativo expone correctamente.
# - Interfaces y mixers USB suelen requerir drivers; mantenerlos actualizados es clave.
# - En macOS/Linux suelen aparecer como “USB Audio Device”, en Windows con el nombre del fabricante.

# Latencia y sincronización
# - Aunque fijes un audio master, debes cuidar la sincronización con el video.
# - WebRTC ajusta automáticamente, pero en RTMP/HLS conviene calibrar buffers y timestamps con ffmpeg/OBS.

# Selección persistente de dispositivos
# - Guarda el deviceId elegido (ej. en localStorage o en tu backend).
# - Así, si el usuario recarga la página, se mantiene el mismo audio master sin volver a pedirlo.

# Fallback inteligente
# - Si el dispositivo elegido se desconecta, tu app debe ofrecer cambiar automáticamente a otro micrófono disponible.
# - Esto evita que la transmisión quede sin audio.

# Monitoreo en tiempo real
# - Usa la Web Audio API (AnalyserNode) para mostrar niveles de audio en la interfaz.
# - El usuario puede validar que el master está enviando señal y ajustar ganancia antes de transmitir.

# Escalabilidad
# - Para pocos espectadores: WebRTC directo funciona bien.
# - Para conciertos/eventos grandes: enviar el stream a un servidor (Nginx RTMP, Wowza, Janus) y distribuir vía CDN.
# - Django sigue siendo el “cerebro” que controla accesos y sesiones.

# En resumen
# - El navegador puede capturar cualquier fuente de audio reconocida por el sistema (micrófono, interfaz, mixer).
# - La clave está en fijar un master de audio con deviceId, mantenerlo constante aunque cambies de cámara,
#   monitorear calidad/latencia y usar Django para control, no para mezcla.


# Fin de la guía.
