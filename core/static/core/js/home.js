// ===================================
// CAMERA STATE MANAGER (SNAPSHOT + WS)
// ===================================
class CameraStatePoller {
  constructor() {
    this.lastState = {};
    this.previewHls = null;
    this.currentPreviewUrl = null;
    this.hasActivePreview = false;
    this.allCameras = {}; // estado acumulado para evitar borrados por updates parciales
    this.start();
  }

  // ============================
  // SNAPSHOT INICIAL
  // ============================
  async start() {
    await this.fetchState();
    console.log('📸 Snapshot inicial de cámaras cargado');
  }

  async fetchState() {
    try {
      const res = await fetch('/estado-camaras/', { cache: 'no-store' });
      const data = await res.json();
      if (data.ok && data.cameras) {
        // Mantener estado completo
        this.allCameras = data.cameras;
        this.syncCameras(this.allCameras);

        // Sincronizar preview si hay canal activo
        if (data.canal && data.canal.en_vivo) {
          setTimeout(() => {
            this.syncPreview({ status: 'on_air', hls_url: data.canal.hls_url });
          }, 300);
        } else {
          this.syncPreview(null);
        }
      }
    } catch (e) {
      console.warn('⚠️ Error snapshot cámaras', e);
    }
  }

  // ============================
  // VERIFICAR STREAM DISPONIBLE
  // ============================
  async waitForStream(url, maxAttempts = 8) {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const response = await fetch(url, { method: 'HEAD', cache: 'no-store' });
        if (response.ok) {
          console.log(`✅ Stream listo: ${url}`);
          return true;
        }
      } catch (e) {
        // Continuar intentando
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    console.warn(`⚠️ Stream no disponible: ${url}`);
    return false;
  }

  // ============================
  // PONER CÁMARA AL AIRE
  // ============================
  async setOnAir(camIndex) {
    const card = document.querySelector(`.camera-card[data-camera="${camIndex}"]`);
    // Mejora: Pasamos el objeto completo para no perder la URL durante el cambio de UI
    const currentCam = this.allCameras[camIndex];
    if (card && currentCam) {
        this.applyState(card, { ...currentCam, status: 'on_air' });
    } else if (card) {
        this.applyState(card, { status: 'on_air' });
    }

    try {
      const res = await fetch(`/poner-al-aire/${camIndex}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() }
      });
      // Forzar preview inmediata en primera vez
      const cam = this.allCameras[camIndex];
      if (cam && cam.hls_url) {
        setTimeout(() => {
          this.syncPreview({ status: 'on_air', hls_url: cam.hls_url });
        }, 200);
      }
    } catch (e) {
      console.warn('⚠️ Error poniendo cámara al aire', e);
    }
  }

  // ============================
  // SINCRONIZAR CÁMARAS
  // ============================
  syncCameras(cameras) {
    let onAirCam = null;

    const grid = document.getElementById('camerasGrid');
    const emptyState = document.getElementById('camerasEmpty');
    const countEl = document.getElementById('activeCamCount');

    if (countEl) countEl.textContent = Object.keys(cameras).length;

    if (Object.keys(cameras).length === 0) {
      if (emptyState) emptyState.style.display = 'block';
      if (grid) grid.innerHTML = '';
      this.syncPreview(null);
      return;
    } else {
      if (emptyState) emptyState.style.display = 'none';
    }

    // Crear o actualizar cámaras (NO borrar por updates parciales)
    Object.entries(cameras).forEach(([index, cam]) => {
      let wrapper = document.querySelector(`.camera-wrapper[data-camera="${index}"]`);
      let card = wrapper ? wrapper.querySelector('.camera-card') : null;

      if (!wrapper && cam.status !== 'offline') {
        card = this.createCameraCard(index);
        wrapper = card ? card.closest('.camera-wrapper') : null;
      }

      if (!card) return;

      // Actualizar estado solo si cambió
      if (this.lastState[index] !== cam.status) {
        this.applyState(card, cam);
        this.lastState[index] = cam.status;
      }

      // Manejo de Video Stream
      if ((cam.status === 'ready' || cam.status === 'on_air') && cam.hls_url) {
        this.ensureVideoElement(card);
        this.attachStreamWithWait(card, cam.hls_url);
      } else {
        this.cleanupVideo(card);
      }

      if (cam.status === 'on_air') onAirCam = cam;
    });

    // No eliminar wrappers aquí. Solo en evento explícito de eliminación.
    this.syncPreview(onAirCam);
  }

  // ============================
  // LIMPIAR VIDEO
  // ============================
  cleanupVideo(card) {
    const video = card.querySelector('video');
    if (video) {
      if (video._hls) {
        video._hls.destroy();
        delete video._hls;
      }
      video.remove();
    }
    const loader = card.querySelector('.video-loader');
    if (loader) loader.remove();
  }

  // ============================
  // PREVIEW PRINCIPAL
  // ============================
  async syncPreview(cam) {
    const video = document.getElementById('mainPreviewVideo');
    const empty = document.getElementById('previewEmpty');
    const liveBadge = document.getElementById('liveBadge');
    const streamStatus = document.getElementById('streamStatus');

    if (!cam || !cam.hls_url) {
      this.destroyPreview();
      if (liveBadge) {
        liveBadge.className = 'live-badge';
        liveBadge.innerHTML = `<span class="live-dot"></span><span>OFFLINE</span>`;
      }
      if (streamStatus) streamStatus.textContent = 'OFFLINE';
      return;
    }

    // Evitar reataches innecesarios
    if (this.currentPreviewUrl === cam.hls_url && this.previewHls) {
      if (liveBadge) {
        liveBadge.className = 'live-badge active';
        liveBadge.innerHTML = `<span class="live-dot"></span><span>EN VIVO</span>`;
      }
      if (streamStatus) streamStatus.textContent = 'EN VIVO';
      if (video) {
        video.style.display = 'block';
        if (empty) empty.style.display = 'none';
      }
      return;
    }

    this.destroyPreview();
    this.currentPreviewUrl = cam.hls_url;
    this.hasActivePreview = true;

    if (video) {
      // Asegurar estilo para evitar borde negro (fix #3)
      video.style.display = 'block';
      video.style.width = '100%';
      video.style.height = '100%';
      video.style.objectFit = 'cover';
    }
    if (empty) empty.style.display = 'none';

    if (liveBadge) {
      liveBadge.className = 'live-badge active';
      liveBadge.innerHTML = `<span class="live-dot"></span><span>EN VIVO</span>`;
    }
    if (streamStatus) streamStatus.textContent = 'EN VIVO';

    // Esperar a que el stream esté disponible (fix #2: primera vez)
    const streamReady = await this.waitForStream(cam.hls_url);
    if (!streamReady) {
      console.error('Preview stream no disponible');
      return;
    }

    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        enableWorker: true,
        maxBufferLength: 10,
        maxMaxBufferLength: 20
      });
      hls.loadSource(cam.hls_url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('📺 Preview cargado');
        video.play().catch(e => console.warn('Error reproducción:', e));
      });
      hls.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          console.error('❌ Error preview:', data.type);
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              hls.recoverMediaError();
              break;
            default:
              this.destroyPreview();
              break;
          }
        }
      });
      this.previewHls = hls;
    } else {
      // Fallback nativo
      video.src = cam.hls_url;
      video.play().catch(() => {});
    }
  }

  destroyPreview() {
    const video = document.getElementById('mainPreviewVideo');
    const empty = document.getElementById('previewEmpty');

    if (this.previewHls) {
      this.previewHls.destroy();
      this.previewHls = null;
    }
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.style.display = 'none';
      // Mantener tamaño para evitar saltos
      video.style.width = '100%';
      video.style.height = '100%';
      video.style.objectFit = 'cover';
    }
    if (empty) empty.style.display = 'flex';

    this.currentPreviewUrl = null;
    this.hasActivePreview = false;
  }

  // ============================
  // CREAR CARD DE CÁMARA
  // ============================
  createCameraCard(index) {
    const grid = document.getElementById('camerasGrid');
    if (!grid) return null;

    const wrapper = document.createElement('div');
    wrapper.className = 'camera-wrapper';
    wrapper.dataset.camera = index;

    wrapper.innerHTML = `
      <div class="camera-external-toolbar" style="display: none;">
        <button class="tool-btn" data-action="mute" title="Silenciar">🎤</button>
        <button class="tool-btn btn-close" data-action="close" title="Desconectar">✕</button>
      </div>
      <div class="camera-card pending" data-camera="${index}">
        <div class="camera-status-badge pending">SOLICITUD</div>
        <div class="camera-number-badge">${index}</div>
        <div class="camera-preview">
          <div class="preview-empty">Conectando...</div>
        </div>
        <div class="camera-info-bar"></div>
      </div>
      <div class="camera-action-container"></div>
    `;

    this.bindToolbarEvents(wrapper, index);
    grid.appendChild(wrapper);
    return wrapper.querySelector('.camera-card');
  }

  // ============================
  // EVENTOS TOOLBAR
  // ============================
  bindToolbarEvents(wrapper, index) {
    wrapper.querySelectorAll('.tool-btn').forEach(btn => {
      btn.onclick = async () => {
        const action = btn.dataset.action;

        if (action === 'mute') {
          const video = wrapper.querySelector('video');
          if (!video) return;
          video.muted = !video.muted;
          btn.textContent = video.muted ? '🔇' : '🎤';
        }

        if (action === 'close') {
          if (!confirm(`¿Desconectar cámara ${index}?`)) return;
          await fetch(`/cerrar-camara/${index}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() }
          });
        }
      };
    });
  }

  // ============================
  // RENDERIZADO DE ESTADO
  // ============================
  applyState(card, cam) {
    const wrapper = card.closest('.camera-wrapper');
    const toolbar = wrapper.querySelector('.camera-external-toolbar');
    const actionArea = wrapper.querySelector('.camera-action-container');
    const badge = card.querySelector('.camera-status-badge');
    const preview = card.querySelector('.camera-preview');
    const bar = card.querySelector('.camera-info-bar');

    // Limpiar clases previas
    card.className = `camera-card ${cam.status}`;
    toolbar.style.display = (cam.status === 'ready' || cam.status === 'on_air') ? 'flex' : 'none';

    switch (cam.status) {
      case 'pending':
        badge.className = 'camera-status-badge pending';
        badge.textContent = 'SOLICITUD';
        if (!preview.querySelector('video') && !preview.querySelector('.video-loader')) {
          preview.innerHTML = `<div class="preview-empty">Intento de conexión</div>`;
        }
        actionArea.innerHTML = '';
        bar.classList.remove('hidden-bar');
        this.ensurePendingActions(card);
        break;

      case 'ready':
        badge.className = 'camera-status-badge ready';
        badge.textContent = 'LISTA';
        bar.innerHTML = '';
        bar.classList.add('hidden-bar');

        // Botón "PONER AL AIRE" externo
        if (!toolbar.querySelector('.btn-on-air-ext')) {
          const btn = document.createElement('button');
          btn.className = 'btn-action-external btn-on-air-ext';
          btn.textContent = 'PONER AL AIRE';
          btn.onclick = () => this.setOnAir(card.dataset.camera);
          toolbar.prepend(btn);
        }

        // Asegurar video sizing (fix #3)
        this.ensureVideoElement(card);
        const v = card.querySelector('video');
        if (v) {
          v.style.width = '100%';
          v.style.height = '100%';
          v.style.objectFit = 'cover';
        }
        break;

      case 'on_air':
        badge.className = 'camera-status-badge on-air';
        badge.innerHTML = `<span class="badge-pulse"></span> EN AIRE`;
        bar.innerHTML = '';
        actionArea.innerHTML = '';
        const btnOnAir = toolbar.querySelector('.btn-on-air-ext');
        if (btnOnAir) btnOnAir.remove();
        break;

      case 'offline':
        badge.className = 'camera-status-badge offline';
        badge.textContent = 'OFFLINE';
        preview.innerHTML = `<div class="preview-empty">Desconectada</div>`;
        actionArea.innerHTML = '';
        bar.innerHTML = '';
        break;
    }
  }

  // ============================
  // ASEGURAR VIDEO ELEMENT
  // ============================
  ensureVideoElement(card) {
    const preview = card.querySelector('.camera-preview');
    // Si ya tiene video, no hacer nada
    if (preview.querySelector('video')) return;

    // Crear estructura completa con sizing estable (fix #3)
    const videoContainer = document.createElement('div');
    videoContainer.style.position = 'relative';
    videoContainer.style.width = '100%';
    videoContainer.style.height = '100%';

    const video = document.createElement('video');
    video.className = 'camera-video';
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.width = '100%';
    video.style.height = '100%';
    video.style.objectFit = 'cover';
    video.style.backgroundColor = '#000';

    const loader = document.createElement('div');
    loader.className = 'video-loader';
    loader.innerHTML = `
      <div class="loader-spinner"></div>
      <div class="loader-text">Cargando...</div>
    `;

    videoContainer.appendChild(video);
    videoContainer.appendChild(loader);
    preview.innerHTML = '';
    preview.appendChild(videoContainer);
  }

  // ============================
  // ADJUNTAR STREAM CON ESPERA
  // ============================
  async attachStreamWithWait(card, url) {
    const video = card.querySelector('video');
    const loader = card.querySelector('.video-loader');
    if (!video) return;

    // Si ya está cargado, no hacer nada
    if (video.dataset.src === url && video._hls) return;

    // Mostrar loader
    if (loader) loader.style.display = 'flex';

    // Esperar a que el stream esté disponible
    const streamReady = await this.waitForStream(url);
    if (!streamReady) {
      if (loader) {
        loader.innerHTML = `
          <div class="loader-error">⚠️</div>
          <div class="loader-text">Stream no disponible</div>
        `;
      }
      return;
    }

    // Cargar stream
    this.attachStream(card, url, loader);
  }

  // ============================
  // ADJUNTAR STREAM
  // ============================
  attachStream(card, url, loader) {
    const video = card.querySelector('video');
    if (!video) return;

    // Destruir HLS previo
    if (video._hls) {
      video._hls.destroy();
      delete video._hls;
    }

    if (window.Hls && Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        enableWorker: true,
        maxBufferLength: 10,
        maxMaxBufferLength: 20
      });
      hls.loadSource(url);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('📹 Stream cargado:', card.dataset.camera);
        video.play()
          .then(() => {
            if (loader) loader.style.display = 'none';
          })
          .catch(e => console.warn('Error reproducción:', e));
      });
      hls.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          console.error('❌ Error HLS:', data.type);
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              hls.recoverMediaError();
              break;
            default:
              hls.destroy();
              if (loader) {
                loader.innerHTML = `
                  <div class="loader-error">❌</div>
                  <div class="loader-text">Error de stream</div>
                `;
                loader.style.display = 'flex';
              }
              break;
          }
        }
      });
      video._hls = hls;
      video.dataset.src = url;
    } else {
      // Fallback nativo
      video.src = url;
      video.play()
        .then(() => { if (loader) loader.style.display = 'none'; })
        .catch(() => {});
      video.dataset.src = url;
    }
  }

  ensurePendingActions(card) {
    const bar = card.querySelector('.camera-info-bar');
    if (bar.dataset.bound) return;
    bar.dataset.bound = '1';

    const index = card.dataset.camera;
    bar.innerHTML = `
      <form class="accept-form">
        <input type="password" name="pin" placeholder="PIN" required>
        <button type="submit">Aceptar</button>
      </form>
      <form class="reject-form">
        <button type="submit">Rechazar</button>
      </form>
    `;

    bar.querySelector('.accept-form').onsubmit = e => {
      e.preventDefault();
      fetch(`/autorizar-camara/${index}/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `pin=${encodeURIComponent(e.target.pin.value)}`
      });
    };

    bar.querySelector('.reject-form').onsubmit = e => {
      e.preventDefault();
      fetch(`/rechazar-camara/${index}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() }
      });
    };
  }
}

// ===================================
// INIT + WEBSOCKET CONNECTION
// ===================================
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('.control-body')) {
    window.cameraPoller = new CameraStatePoller();
  }

  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(`${protocol}://${location.host}/ws/panel/`);

  ws.onopen = () => console.log('🟢 WebSocket conectado');
  ws.onclose = () => console.log('🔴 WebSocket desconectado');

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (!window.cameraPoller) return;

    switch (data.tipo) {
      case 'estado_camaras':
        // Snapshot completo
        window.cameraPoller.allCameras = data.cameras || {};
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);
        break;

      case 'camara_actualizada':
        // Actualización parcial
        
        // --- CORRECCIÓN BUG IMAGENES DUPLICADAS (Realtime) ---
        // Si el backend nos manda la URL del programa (output) porque la cámara está 'on_air',
        // nosotros la ignoramos y mantenemos la URL de entrada (input) si ya la teníamos.
        // Esto asegura que la tarjeta pequeña siempre muestre la cámara individual.
        
        const currentCam = window.cameraPoller.allCameras[data.cam_index] || {};
        let newUrl = data.hls_url;

        if (data.estado === 'on_air' && currentCam.hls_url) {
            // Si ya teníamos una URL válida (la de source), la mantenemos
            // aunque el backend intente darnos la del programa.
            newUrl = currentCam.hls_url;
        }

        window.cameraPoller.allCameras[data.cam_index] = {
          ...currentCam,
          status: data.estado,
          hls_url: newUrl,
          authorized: data.authorized
        };
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);

        // Primera vez al aire: forzar preview principal (este SÍ usa la del programa si el backend quiere)
        // Pero generalmente el preview principal usa el evento 'estado_canal'.
        // Este fallback es por si acaso.
        if (data.estado === 'on_air' && data.hls_url) {
          setTimeout(() => {
            // Aquí pasamos explícitamente data.hls_url por si queremos que el preview grande
            // se actualice, aunque el preview grande suele escuchar 'estado_canal'.
            // Si data.hls_url es la del programa, está bien para el preview principal.
            window.cameraPoller.syncPreview({ status: 'on_air', hls_url: data.hls_url });
          }, 200);
        }
        break;

      case 'camara_eliminada':
        // Eliminar explícitamente
        const cardWrapper = document.querySelector(`.camera-wrapper[data-camera="${data.cam_index}"]`);
        if (cardWrapper) cardWrapper.remove();
        delete window.cameraPoller.lastState[data.cam_index];
        delete window.cameraPoller.allCameras[data.cam_index];
        // Si no quedan cámaras, actualizar UI
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);
        break;

      case 'estado_canal':
        // Estado del canal/preview
        const canalData = data.en_vivo ? { status: 'on_air', hls_url: data.hls_url } : null;
        window.cameraPoller.syncPreview(canalData);
        break;
    }
  };

  const stopBtn = document.getElementById('btnStopStream');
  const volume = document.getElementById('previewVolume');
  const video = document.getElementById('mainPreviewVideo');
  const volValue = document.getElementById('volumeValue');

  if (stopBtn) {
    stopBtn.addEventListener('click', async () => {
      if (!window.cameraPoller || !window.cameraPoller.hasActivePreview) return;
      if (confirm('¿Detener transmisión en vivo?')) {
        await fetch('/detener-transmision/', {
          method: 'POST',
          headers: { 'X-CSRFToken': getCSRFToken() }
        });
      }
    });
  }

  if (volume && video) {
    volume.addEventListener('input', (e) => {
      video.muted = false;
      video.volume = e.target.value;
      if (volValue) volValue.textContent = Math.round(e.target.value * 100) + '%';
    });
  }
});