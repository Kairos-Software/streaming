// ===================================
// CAMERA STATE MANAGER (SNAPSHOT + WS)
// ===================================
class CameraStatePoller {
    constructor() {
        this.lastState = {};
        this.previewHls = null;
        this.currentPreviewUrl = null;
        this.hasActivePreview = false;

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
                this.syncCameras(data.cameras);
            }
        } catch (e) {
            console.warn('⚠️ Error snapshot cámaras', e);
        }
    }

    // ============================
    // PONER CÁMARA AL AIRE
    // ============================
    async setOnAir(camIndex) {
        const card = document.querySelector(`.camera-card[data-camera="${camIndex}"]`);
        if (card) this.applyState(card, { status: 'on_air' });

        try {
            await fetch(`/poner-al-aire/${camIndex}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCSRFToken() }
            });
        } catch (e) {
            console.warn('⚠️ Error poniendo cámara al aire', e);
        }
    }

    // ============================
    // SINCRONIZAR CÁMARAS
    // ============================
    syncCameras(cameras) {
        let onAirCam = null;
        const backendIndexes = new Set(Object.keys(cameras));

        // Eliminar wrappers que ya no existen
        document.querySelectorAll('.camera-wrapper').forEach(wrapper => {
            const index = wrapper.dataset.camera;
            if (!backendIndexes.has(index)) {
                const video = wrapper.querySelector('video');
                if (video && video._hls) video._hls.destroy();
                wrapper.remove();
                delete this.lastState[index];
            }
        });

        Object.entries(cameras).forEach(([index, cam]) => {
            let wrapper = document.querySelector(`.camera-wrapper[data-camera="${index}"]`);
            let card = wrapper ? wrapper.querySelector('.camera-card') : null;

            // Crear card si no existe y no está offline
            if (!wrapper && cam.status !== 'offline') card = this.createCameraCard(index);
            if (!card) return;

            // Actualizar estado solo si cambió
            if (this.lastState[index] !== cam.status) {
                this.applyState(card, cam);
                this.lastState[index] = cam.status;
            }

            // Video stream
            if ((cam.status === 'ready' || cam.status === 'on_air') && cam.hls_url) {
                this.ensureVideoElement(card);
                this.attachStream(card, cam.hls_url);
            } else {
                // Si no hay HLS, limpiar video
                const video = card.querySelector('video');
                if (video) {
                    if (video._hls) video._hls.destroy();
                    video.remove();
                }
            }

            if (cam.status === 'on_air') onAirCam = cam;
        });

        this.syncPreview(onAirCam);
    }

    // ============================
    // PREVIEW PRINCIPAL
    // ============================
    syncPreview(cam) {
        const video = document.getElementById('mainPreviewVideo');
        const empty = document.getElementById('previewEmpty');
        const globalStatus = document.getElementById('globalStatus');

        if (!cam || !cam.hls_url) {
            this.destroyPreview();
            if (globalStatus) {
                globalStatus.className = 'header-status-badge offline';
                globalStatus.textContent = 'OFFLINE';
            }
            return;
        }

        if (this.currentPreviewUrl === cam.hls_url) return;

        this.destroyPreview();
        this.currentPreviewUrl = cam.hls_url;
        this.hasActivePreview = true;

        video.style.display = 'block';
        empty.style.display = 'none';

        if (window.Hls && Hls.isSupported()) {
            const hls = new Hls({ lowLatencyMode: true });
            hls.loadSource(cam.hls_url);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
            this.previewHls = hls;
        } else {
            video.src = cam.hls_url;
            video.play().catch(() => {});
        }

        if (globalStatus) {
            globalStatus.className = 'header-status-badge on-air';
            globalStatus.innerHTML = `<span class="status-pulse"></span> EN VIVO`;
        }
    }

    destroyPreview() {
        const video = document.getElementById('mainPreviewVideo');

        if (this.previewHls) {
            this.previewHls.destroy();
            this.previewHls = null;
        }

        if (video) {
            video.pause();
            video.removeAttribute('src');
            video.load();
        }

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
                <button class="tool-btn" data-action="mute">🎤</button>
                <button class="tool-btn btn-close" data-action="close">✕</button>
            </div>

            <div class="camera-card pending" data-camera="${index}">
                <div class="camera-status-badge pending">SOLICITUD</div>
                <div class="camera-number-badge">${index}</div>
                <div class="camera-preview">
                    <div class="preview-empty">Intento de conexión detectado</div>
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
    // TOOLBAR
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
    // RENDER ESTADO
    // ============================
    applyState(card, cam) {
        const wrapper = card.closest('.camera-wrapper');
        const toolbar = wrapper.querySelector('.camera-external-toolbar');
        const actionArea = wrapper.querySelector('.camera-action-container');
        const badge = card.querySelector('.camera-status-badge');
        const preview = card.querySelector('.camera-preview');
        const bar = card.querySelector('.camera-info-bar');

        card.className = `camera-card ${cam.status}`;
        toolbar.style.display = (cam.status === 'ready' || cam.status === 'on_air') ? 'flex' : 'none';

        switch(cam.status) {
            case 'pending':
                badge.textContent = 'SOLICITUD';
                preview.innerHTML = `<div class="preview-empty">Intento de conexión detectado</div>`;
                actionArea.innerHTML = '';
                this.ensurePendingActions(card);
                break;

            case 'ready':
                badge.textContent = 'LISTA';
                bar.innerHTML = '';
                bar.classList.add('hidden-bar');

                if (!toolbar.querySelector('.btn-on-air-ext')) {
                    toolbar.insertAdjacentHTML('afterbegin', `
                        <button class="btn-action-external btn-on-air-ext">
                            PONER AL AIRE
                        </button>
                    `);
                    toolbar.querySelector('.btn-on-air-ext').onclick =
                        () => this.setOnAir(card.dataset.camera);
                }
                break;

            case 'on_air':
                badge.innerHTML = `<span class="badge-pulse"></span> EN AIRE`;
                bar.innerHTML = '';
                actionArea.innerHTML = '';
                break;

            case 'offline':
                badge.textContent = 'OFFLINE';
                preview.innerHTML = `<div class="preview-empty">Cámara desconectada</div>`;
                actionArea.innerHTML = '';
                bar.innerHTML = '';
                break;
        }
    }

    ensureVideoElement(card) {
        const preview = card.querySelector('.camera-preview');
        if (!preview.querySelector('video')) {
            preview.innerHTML = `<video class="camera-video" autoplay muted playsinline></video>`;
        }
    }

    attachStream(card, url) {
        if (!window.Hls || !Hls.isSupported()) return;
        const video = card.querySelector('video');
        if (!video || video.dataset.src === url) return;

        if (video._hls) video._hls.destroy();

        const hls = new Hls({ lowLatencyMode: true });
        hls.loadSource(url);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));

        video._hls = hls;
        video.dataset.src = url;
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
// INIT + WEBSOCKET
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.control-body')) {
        window.cameraPoller = new CameraStatePoller();
    }

    const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${location.host}/ws/panel/`);

    ws.onopen = () => console.log('🟢 WebSocket conectado');

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('📩 WS:', data);

        if (!window.cameraPoller) return;

        switch (data.tipo) {
            case 'estado_camaras':
                window.cameraPoller.syncCameras(data.cameras);
                break;

            case 'camara_actualizada':
                const camObj = {};
                camObj[data.cam_index] = {
                    status: data.estado,
                    authorized: data.authorized,
                    hls_url: data.hls_url
                };
                window.cameraPoller.syncCameras(camObj);
                break;

            case 'camara_eliminada':
                const cardWrapper = document.querySelector(`.camera-wrapper[data-camera="${data.cam_index}"]`);
                if (cardWrapper) cardWrapper.remove();
                delete window.cameraPoller.lastState[data.cam_index];
                break;

            case 'estado_canal':
                window.cameraPoller.syncPreview(data.en_vivo ? data : null);
                break;
        }
    };
});
