// ===================================
// CSRF TOKEN HELPER
// ===================================
function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue;
}

// ===================================
// CAMERA STATE MANAGER (SNAPSHOT + WS)
// ===================================
class CameraStatePoller {
  constructor() {
    this.lastState = {};
    this.previewHls = null;
    this.currentPreviewUrl = null;
    this.hasActivePreview = false;
    this.allCameras = {};
    this.activePlatforms = {};
    this.start();
  }

  async start() {
    await this.fetchState();
    console.log('📸 Snapshot inicial de cámaras cargado');
  }

  async fetchState() {
    try {
      const res = await fetch('/estado-camaras/', { cache: 'no-store' });
      const data = await res.json();
      if (data.ok && data.cameras) {
        Object.entries(data.cameras).forEach(([index, cam]) => {
          const prevCam = this.allCameras[index];
          if (cam.status === 'on_air' && prevCam && prevCam.hls_url && cam.hls_url !== prevCam.hls_url) {
            cam.hls_url = prevCam.hls_url;
          }
        });

        this.allCameras = data.cameras;
        this.syncCameras(this.allCameras);

        const currentOnAirCam = Object.values(data.cameras).find(cam => cam.status === 'on_air');
        
        if (currentOnAirCam && currentOnAirCam.hls_url) {
          setTimeout(() => {
            this.syncPreview({ status: 'on_air', hls_url: currentOnAirCam.hls_url });
          }, 300);
        } else if (data.canal && data.canal.en_vivo && data.canal.hls_url) {
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

  async waitForStream(url, maxAttempts = 8) {
    for (let i = 0; i < maxAttempts; i++) {
      try {
        const response = await fetch(url, { method: 'HEAD', cache: 'no-store' });
        if (response.ok) {
          console.log(`✅ Stream listo: ${url}`);
          return true;
        }
      } catch (e) {}
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    console.warn(`⚠️ Stream no disponible: ${url}`);
    return false;
  }

  async setOnAir(camIndex) {
    const card = document.querySelector(`.camera-card[data-camera="${camIndex}"]`);
    const currentCam = this.allCameras[camIndex];
    if (card && currentCam) {
        this.applyState(card, { ...currentCam, status: 'on_air' });
    } else if (card) {
        this.applyState(card, { status: 'on_air' });
    }

    try {
      await fetch(`/poner-al-aire/${camIndex}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCSRFToken() }
      });
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

    Object.entries(cameras).forEach(([index, cam]) => {
      let wrapper = document.querySelector(`.camera-wrapper[data-camera="${index}"]`);
      let card = wrapper ? wrapper.querySelector('.camera-card') : null;

      if (!wrapper && cam.status !== 'offline') {
        card = this.createCameraCard(index);
        wrapper = card ? card.closest('.camera-wrapper') : null;
      }

      if (!card) return;

      if ((cam.status === 'ready' || cam.status === 'on_air') && cam.hls_url) {
        this.ensureVideoElement(card);
        this.attachStreamWithWait(card, cam.hls_url);
      } else {
        this.cleanupVideo(card);
      }

      if (this.lastState[index] !== cam.status) {
        this.applyState(card, cam);
        this.lastState[index] = cam.status;
      }

      if (cam.status === 'on_air') onAirCam = cam;
    });

    this.syncPreview(onAirCam);
  }

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

  async syncPreview(cam) {
    const video = document.getElementById('mainPreviewVideo');
    const empty = document.getElementById('previewEmpty');
    const liveBadge = document.getElementById('liveBadge');
    const streamStatus = document.getElementById('streamStatus');
    const btnRestream = document.getElementById('btnRestream');

    if (!cam || !cam.hls_url) {
      this.destroyPreview();
      if (liveBadge) {
        liveBadge.className = 'live-badge';
        liveBadge.innerHTML = `<span class="live-dot"></span><span>OFFLINE</span>`;
      }
      if (streamStatus) streamStatus.textContent = 'OFFLINE';
      if (btnRestream) btnRestream.style.display = 'none';
      this.updateRestreamStatus();
      return;
    }

    if (this.currentPreviewUrl === cam.hls_url && this.previewHls) {
      if (liveBadge) {
        liveBadge.className = 'live-badge active';
        liveBadge.innerHTML = `<span class="live-dot"></span><span>EN VIVO</span>`;
      }
      if (streamStatus) streamStatus.textContent = 'EN VIVO';
      if (btnRestream) btnRestream.style.display = 'flex';
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
    if (btnRestream) btnRestream.style.display = 'flex';

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
      video.src = cam.hls_url;
      video.play().catch(() => {});
    }
  }

  destroyPreview() {
    const video = document.getElementById('mainPreviewVideo');
    const empty = document.getElementById('previewEmpty');
    const btnRestream = document.getElementById('btnRestream');

    if (this.previewHls) {
      this.previewHls.destroy();
      this.previewHls = null;
    }
    if (video) {
      video.pause();
      video.removeAttribute('src');
      video.load();
      video.style.display = 'none';
      video.style.width = '100%';
      video.style.height = '100%';
      video.style.objectFit = 'cover';
    }
    if (empty) empty.style.display = 'flex';
    if (btnRestream) btnRestream.style.display = 'none';

    this.currentPreviewUrl = null;
    this.hasActivePreview = false;
    this.updateRestreamStatus();
  }

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

  applyState(card, cam) {
    const wrapper = card.closest('.camera-wrapper');
    const toolbar = wrapper.querySelector('.camera-external-toolbar');
    const actionArea = wrapper.querySelector('.camera-action-container');
    const badge = card.querySelector('.camera-status-badge');
    const preview = card.querySelector('.camera-preview');
    const bar = card.querySelector('.camera-info-bar');

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
          
          // Muestra los botones flotantes (X y Mic)
          toolbar.style.display = 'flex'; 
  
          this.ensureVideoElement(card);
          const v = card.querySelector('video');
          if (v) {
            v.style.width = '100%';
            v.style.height = '100%';
            v.style.objectFit = 'cover';
          }
  
          // Inyecta el botón "AL AIRE" central (Overlay)
          const previewContainer = card.querySelector('.camera-preview');
          if (!previewContainer.querySelector('.ready-action-overlay')) {
              const overlay = document.createElement('div');
              overlay.className = 'ready-action-overlay';
              overlay.innerHTML = `
                  <button class="btn-overlay-live">
                      <span class="material-icons">sensors</span>
                      AL AIRE
                  </button>
              `;
              
              overlay.querySelector('button').onclick = (e) => {
                  e.stopPropagation();
                  this.setOnAir(card.dataset.camera);
              };
  
              previewContainer.appendChild(overlay);
          }
          break;

      case 'on_air':
        badge.className = 'camera-status-badge on-air';
        badge.innerHTML = `<span class="badge-pulse"></span> EN AIRE`;
        bar.innerHTML = '';
        bar.classList.add('hidden-bar');
        actionArea.innerHTML = '';
        const btnOnAir = toolbar.querySelector('.btn-on-air-ext');
        if (btnOnAir) btnOnAir.remove();
        
        const videoOnAir = card.querySelector('video');
        if (videoOnAir) {
          videoOnAir.style.width = '100%';
          videoOnAir.style.height = '100%';
          videoOnAir.style.objectFit = 'cover';
        }
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

  ensureVideoElement(card) {
    const preview = card.querySelector('.camera-preview');
    if (preview.querySelector('video')) return;

    preview.style.position = 'relative';
    preview.innerHTML = '';
    
    const video = document.createElement('video');
    video.className = 'camera-video';
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.position = 'absolute';
    video.style.top = '0';
    video.style.left = '0';
    video.style.width = '100%';
    video.style.height = '100%';
    video.style.objectFit = 'cover';
    video.style.backgroundColor = '#000';

    const loader = document.createElement('div');
    loader.className = 'video-loader';
    loader.style.position = 'absolute';
    loader.style.top = '50%';
    loader.style.left = '50%';
    loader.style.transform = 'translate(-50%, -50%)';
    loader.style.zIndex = '10';
    loader.innerHTML = `
      <div class="loader-spinner"></div>
      <div class="loader-text">Cargando...</div>
    `;

    preview.appendChild(video);
    preview.appendChild(loader);
  }

  async attachStreamWithWait(card, url) {
    const video = card.querySelector('video');
    const loader = card.querySelector('.video-loader');
    if (!video) return;

    if (video.dataset.src === url && video._hls) return;

    if (loader) loader.style.display = 'flex';

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

    this.attachStream(card, url, loader);
  }

  attachStream(card, url, loader) {
    const video = card.querySelector('video');
    if (!video) return;

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
    const previewArea = card.querySelector('.camera-preview');
    
    // Limpiamos preview
    previewArea.innerHTML = '';
    
    // Contenedor Flex Vertical Centrado
    const container = document.createElement('div');
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.alignItems = 'center';
    container.style.justifyContent = 'center';
    container.style.width = '100%';
    container.style.height = '100%'; // Ocupa todo el alto
    container.style.padding = '16px'; // Padding para que no toque bordes
    
    // Icono y Texto
    const headerHtml = `
        <div style="text-align:center; margin-bottom:12px;">
            <div style="font-size: 28px; color: var(--status-pending); margin-bottom: 4px;">
                <span class="material-icons">lock</span>
            </div>
            <div class="preview-empty" style="font-size:10px;">Solicitud</div>
        </div>
    `;

    // Wrapper de Acciones (Input + Botones)
    const actionsWrapper = document.createElement('div');
    actionsWrapper.className = 'pending-actions-wrapper';
    
    actionsWrapper.innerHTML = `
      <form class="accept-row">
        <input type="password" name="pin" placeholder="PIN" maxlength="6" autocomplete="off" required>
        <button type="submit" class="btn-accept-icon" title="Autorizar">
            <span class="material-icons">check</span>
        </button>
      </form>
      <button type="button" class="btn-reject-full" title="Rechazar">
        <span class="material-icons" style="font-size:14px;">close</span> Rechazar
      </button>
    `;

    container.innerHTML = headerHtml;
    container.appendChild(actionsWrapper);
    previewArea.appendChild(container);

    // Lógica JS (Submit / Click)
    const form = actionsWrapper.querySelector('.accept-row');
    const rejectBtn = actionsWrapper.querySelector('.btn-reject-full');

    form.onsubmit = e => {
      e.preventDefault();
      fetch(`/autorizar-camara/${index}/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: `pin=${encodeURIComponent(form.pin.value)}`
      });
    };

    rejectBtn.onclick = e => {
      e.preventDefault();
      if(confirm('¿Rechazar conexión?')) {
          fetch(`/rechazar-camara/${index}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() }
          });
      }
    };
  }

  // ===================================
  // RESTREAM MANAGEMENT
  // ===================================
  addActivePlatform(platform) {
    this.activePlatforms[platform] = {
      status: 'streaming',
      startedAt: Date.now()
    };
    this.updateRestreamStatus();
  }

  removePlatform(platform) {
    delete this.activePlatforms[platform];
    this.updateRestreamStatus();
  }

  updatePlatformStatus(platform, status) {
    if (this.activePlatforms[platform]) {
      this.activePlatforms[platform].status = status;
      this.updateRestreamStatus();
    }
  }

  updateRestreamStatus() {
    const panel = document.getElementById('restreamStatusPanel');
    const container = document.getElementById('restreamPlatformsActive');
    
    if (!panel || !container) return;

    const activePlatformsList = Object.keys(this.activePlatforms);

    if (activePlatformsList.length === 0) {
      panel.style.display = 'none';
      return;
    }

    panel.style.display = 'block';
    container.innerHTML = '';

    const platformIcons = {
      youtube: { color: '#ff0000', name: 'YouTube' },
      facebook: { color: '#1877f2', name: 'Facebook' },
      twitch: { color: '#9146ff', name: 'Twitch' },
      instagram: { color: '#e4405f', name: 'Instagram' }
    };

    activePlatformsList.forEach(platform => {
      const data = this.activePlatforms[platform];
      const config = platformIcons[platform] || { color: '#6b7280', name: platform };
      
      const badge = document.createElement('div');
      badge.className = 'restream-platform-badge';
      badge.dataset.platform = platform;
      badge.dataset.status = data.status;

      const statusIcon = data.status === 'streaming' 
        ? `<span class="platform-status-dot streaming"></span>` 
        : data.status === 'error'
        ? `<span class="platform-status-dot error"></span>`
        : `<span class="platform-status-dot"></span>`;

      badge.innerHTML = `
        ${statusIcon}
        <span class="platform-badge-name">${config.name}</span>
        <button class="platform-stop-btn" data-platform="${platform}" title="Detener ${config.name}">
          <svg viewBox="0 0 24 24" width="14" height="14">
            <rect x="6" y="6" width="12" height="12" rx="1" fill="currentColor"/>
          </svg>
        </button>
      `;

      container.appendChild(badge);

      const stopBtn = badge.querySelector('.platform-stop-btn');
      stopBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm(`¿Detener retransmisión en ${config.name}?`)) {
          await this.stopPlatformRestream(platform);
        }
      });
    });
  }

  async stopPlatformRestream(platform) {
    try {
      const response = await fetch(`/multistream/api/restream/stop/${platform}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCSRFToken()
        }
      });

      const data = await response.json();

      if (data.ok) {
        console.log(`✅ ${platform} detenido`);
        this.removePlatform(platform);
      } else {
        throw new Error(data.message || 'Error desconocido');
      }

    } catch (error) {
      console.error(`Error deteniendo ${platform}:`, error);
      alert(`Error al detener ${platform}: ${error.message}`);
      this.updatePlatformStatus(platform, 'error');
    }
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
        window.cameraPoller.allCameras = data.cameras || {};
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);
        break;

      case 'camara_actualizada':
        const currentCam = window.cameraPoller.allCameras[data.cam_index] || {};
        let newUrl = data.hls_url;

        if (data.estado === 'on_air' && currentCam.hls_url) {
            newUrl = currentCam.hls_url;
        }

        window.cameraPoller.allCameras[data.cam_index] = {
          ...currentCam,
          status: data.estado,
          hls_url: newUrl,
          authorized: data.authorized
        };
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);

        if (data.estado === 'on_air' && data.hls_url) {
          setTimeout(() => {
            window.cameraPoller.syncPreview({ status: 'on_air', hls_url: data.hls_url });
          }, 200);
        }
        break;

      case 'camara_eliminada':
        const cardWrapper = document.querySelector(`.camera-wrapper[data-camera="${data.cam_index}"]`);
        if (cardWrapper) cardWrapper.remove();
        delete window.cameraPoller.lastState[data.cam_index];
        delete window.cameraPoller.allCameras[data.cam_index];
        window.cameraPoller.syncCameras(window.cameraPoller.allCameras);
        break;

      case 'estado_canal':
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

  // ===================================
  // RETRANSMISIÓN - MODAL CONTROL
  // ===================================
  const restreamModal = document.getElementById('restreamModal');
  const btnRestream = document.getElementById('btnRestream');
  const btnCloseModal = document.getElementById('btnCloseModal');
  const btnCancelRestream = document.getElementById('btnCancelRestream');
  const btnStartRestream = document.getElementById('btnStartRestream');

  if (btnRestream) {
    btnRestream.addEventListener('click', () => {
      if (restreamModal) {
        restreamModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
      }
    });
  }

  const closeModal = () => {
    if (restreamModal) {
      restreamModal.style.display = 'none';
      document.body.style.overflow = 'auto';
    }
  };

  if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
  if (btnCancelRestream) btnCancelRestream.addEventListener('click', closeModal);

  if (restreamModal) {
    restreamModal.addEventListener('click', (e) => {
      if (e.target.classList.contains('restream-modal-overlay') || e.target === restreamModal) {
        closeModal();
      }
    });
  }

  if (btnStartRestream) {
    btnStartRestream.addEventListener('click', async () => {
      const selectedPlatforms = Array.from(
        document.querySelectorAll('input[name="platform"]:checked')
      ).map(input => input.value);

      if (selectedPlatforms.length === 0) {
        alert('Por favor selecciona al menos una plataforma');
        return;
      }

      console.log('🚀 Iniciando retransmisión en:', selectedPlatforms);
      
      const csrfToken = getCSRFToken();
      console.log('🔑 CSRF Token:', csrfToken ? 'OK' : '❌ NO ENCONTRADO');
      
      btnStartRestream.disabled = true;
      const originalHTML = btnStartRestream.innerHTML;
      btnStartRestream.innerHTML = '<span>Iniciando...</span>';

      try {
        console.log('📡 Enviando petición a:', '/multistream/api/restream/start/');
        
        const response = await fetch('/multistream/api/restream/start/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
          },
          body: JSON.stringify({ platforms: selectedPlatforms })
        });

        console.log('📥 Status:', response.status);

        if (!response.ok) {
          const errorText = await response.text();
          console.error('❌ Error del servidor:', errorText);
          throw new Error(`Error HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ Respuesta:', data);

        console.log('📋 OK?', data.ok);
        console.log('📋 Resultados completos:', data.resultados);
        if (data.resultados && data.resultados.length > 0) {
          data.resultados.forEach((r, i) => {
            console.log(`   [${i}] Platform: ${r.platform}`);
            console.log(`   [${i}] Success: ${r.success}`);
            console.log(`   [${i}] Message: ${r.message}`);
          });
        }

        if (data.ok) {
          let exitosas = [];
          let fallidas = [];

          data.resultados.forEach(resultado => {
            if (resultado.success) {
              exitosas.push(resultado.platform);
              window.cameraPoller.addActivePlatform(resultado.platform);
            } else {
              fallidas.push(`${resultado.platform}: ${resultado.message}`);
            }
          });

          if (exitosas.length > 0) {
            alert(`✅ Retransmisión iniciada en: ${exitosas.join(', ')}`);
          }

          if (fallidas.length > 0) {
            alert(`⚠️ Errores:\n${fallidas.join('\n')}`);
          }

          closeModal();
        } else {
          throw new Error(data.error || 'Error desconocido');
        }

      } catch (error) {
        console.error('💥 Error:', error);
        alert(`❌ Error: ${error.message}\n\nRevisa la consola (F12)`);
      } finally {
        btnStartRestream.disabled = false;
        btnStartRestream.innerHTML = originalHTML;
      }
    });
  }
});