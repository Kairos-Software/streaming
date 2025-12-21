// ===================================
// CONTROL PANEL
// ===================================
class ControlPanel {
    constructor() {
        console.log('🎛 ControlPanel iniciado');
    }
}

// ===================================
// CAMERA STATE POLLER
// ===================================
class CameraStatePoller {
    constructor(interval = 3000) {
        this.interval = interval;
        this.lastState = {};
        this.previewHls = null;
        this.currentPreviewUrl = null;
        this.start();
    }

    start() {
        this.fetchState();
        this.timer = setInterval(() => this.fetchState(), this.interval);
        console.log('🔄 Polling cámaras iniciado');
    }

    async fetchState() {
        try {
            const res = await fetch('/estado-camaras/', { cache: 'no-store' });
            const data = await res.json();
            if (data.ok) this.syncCameras(data.cameras);
        } catch (e) {
            console.warn('⚠️ Error polling cámaras', e);
        }
    }

    async setOnAir(camIndex) {
        try {
            await fetch(`/poner-al-aire/${camIndex}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCSRFToken() }
            });
        } catch (e) {
            console.warn('⚠️ Error poniendo cámara al aire', e);
        }
    }

    // ===================================
    // SYNC CAMERAS
    // ===================================
    syncCameras(cameras) {
        let onAirCam = null;

        Object.entries(cameras).forEach(([index, cam]) => {
            let card = document.querySelector(`.camera-card[data-camera="${index}"]`);

            // crear si no existe (INCLUYE pending)
            if (!card && cam.status !== 'offline') {
                card = this.createCameraCard(index);
            }

            // eliminar offline
            if (cam.status === 'offline' && card) {
                this.destroyStream(card);
                card.remove();
                delete this.lastState[index];
                return;
            }

            if (!card) return;

            if (this.lastState[index] !== cam.status) {
                this.applyState(card, cam);
                this.lastState[index] = cam.status;
            }

            if (cam.status === 'on_air') {
                onAirCam = cam;
            }
        });

        this.syncPreview(onAirCam);
    }

    // ===================================
    // PREVIEW FINAL
    // ===================================
    syncPreview(cam) {
        const video = document.getElementById('mainPreviewVideo');
        const empty = document.getElementById('previewEmpty');
        const globalStatus = document.getElementById('globalStatus');

        if (!cam || !cam.hls_url) {
            this.destroyPreview();
            video.style.display = 'none';
            empty.style.display = 'flex';
            globalStatus.className = 'header-status-badge offline';
            globalStatus.innerHTML = `<span class="status-pulse"></span> SIN TRANSMISIÓN`;
            return;
        }

        if (this.currentPreviewUrl === cam.hls_url) return;
        this.currentPreviewUrl = cam.hls_url;

        this.destroyPreview();

        video.style.display = 'block';
        empty.style.display = 'none';

        if (window.Hls && Hls.isSupported()) {
            const hls = new Hls({ lowLatencyMode: true });
            hls.loadSource(cam.hls_url);
            hls.attachMedia(video);

            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                video.play().catch(() => {});
            });

            this.previewHls = hls;
        } else {
            video.src = cam.hls_url;
            video.play().catch(() => {});
        }

        globalStatus.className = 'header-status-badge on-air';
        globalStatus.innerHTML = `<span class="status-pulse"></span> EN VIVO`;
    }

    destroyPreview() {
        if (this.previewHls) {
            this.previewHls.destroy();
            this.previewHls = null;
        }
        this.currentPreviewUrl = null;
    }

    // ===================================
    // CAMERA CARD
    // ===================================
    createCameraCard(index) {
        const grid = document.getElementById('camerasGrid');
        if (!grid) return null;

        const card = document.createElement('div');
        card.className = 'camera-card pending';
        card.dataset.camera = index;

        card.innerHTML = `
            <div class="camera-status-badge pending">SOLICITUD</div>
            <div class="camera-number-badge">${index}</div>
            <div class="camera-preview">
                <div class="preview-empty">Intento de conexión detectado</div>
            </div>
            <div class="camera-info-bar"></div>
        `;

        grid.appendChild(card);
        return card;
    }

    applyState(card, cam) {
        const badge = card.querySelector('.camera-status-badge');
        const preview = card.querySelector('.camera-preview');
        const bar = card.querySelector('.camera-info-bar');

        card.className = `camera-card ${cam.status}`;

        if (cam.status === 'pending') {
            this.destroyStream(card);
            badge.className = 'camera-status-badge pending';
            badge.textContent = 'SOLICITUD';
            preview.innerHTML = `<div class="preview-empty">Intento de conexión detectado</div>`;
            this.ensurePendingActions(card);
        }

        if (cam.status === 'ready') {
            badge.className = 'camera-status-badge ready';
            badge.textContent = 'LISTA';

            bar.innerHTML = `<button class="btn-on-air">PONER AL AIRE</button>`;
            bar.querySelector('.btn-on-air').onclick = () =>
                this.setOnAir(card.dataset.camera);

            this.ensureVideoElement(card);
            this.attachStream(card, cam.hls_url);
        }

        if (cam.status === 'on_air') {
            badge.className = 'camera-status-badge on-air';
            badge.innerHTML = `<span class="badge-pulse"></span> EN AIRE`;
            bar.innerHTML = '';
        }
    }

    // ===================================
    // STREAM CARD
    // ===================================
    ensureVideoElement(card) {
        const preview = card.querySelector('.camera-preview');
        if (preview.querySelector('video')) return;
        preview.innerHTML = `<video class="camera-video" autoplay muted playsinline></video>`;
    }

    attachStream(card, url) {
        if (!window.Hls || !Hls.isSupported() || !url) return;
        const video = card.querySelector('video');
        if (!video || video._hls) return;

        const hls = new Hls({ lowLatencyMode: true });
        hls.loadSource(url);
        hls.attachMedia(video);
        video._hls = hls;
    }

    destroyStream(card) {
        const video = card.querySelector('video');
        if (video?._hls) {
            video._hls.destroy();
            video._hls = null;
        }
    }

    // ===================================
    // PENDING ACTIONS
    // ===================================
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

        bar.querySelector('.accept-form').onsubmit = async e => {
            e.preventDefault();
            await fetch(`/autorizar-camara/${index}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRFToken(),
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: `pin=${encodeURIComponent(e.target.pin.value)}`
            });
        };

        bar.querySelector('.reject-form').onsubmit = async e => {
            e.preventDefault();
            await fetch(`/rechazar-camara/${index}/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCSRFToken() }
            });
            card.remove();
        };
    }
}

// ===================================
// INIT
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('.control-body')) {
        new ControlPanel();
        new CameraStatePoller();
    }
});

// ===================================
// CSRF
// ===================================
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content;
}
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('mainPreviewVideo');
    const stopBtn = document.getElementById('btnStopStream');
    const volume = document.getElementById('previewVolume');

    if (!video) return;

    // 🔊 VOLUMEN
    volume?.addEventListener('input', () => {
        video.muted = false;
        video.volume = volume.value;
    });

    // ⏹ DETENER TRANSMISIÓN
    stopBtn?.addEventListener('click', async () => {
        if (!confirm('¿Detener transmisión actual?')) return;

        await fetch('/detener-transmision/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCSRFToken() }
        });
    });
});

// ===================================
// MENU
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    const userInfo = document.getElementById('userInfo');
    const userMenu = document.getElementById('userMenu');

    if (!userInfo || !userMenu) return;

    userInfo.addEventListener('click', e => {
        e.stopPropagation();
        userMenu.style.display =
            userMenu.style.display === 'block' ? 'none' : 'block';
    });

    document.addEventListener('click', () => {
        userMenu.style.display = 'none';
    });
});
