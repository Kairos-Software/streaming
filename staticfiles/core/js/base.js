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
        this.hasActivePreview = false;

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
            if (data.ok && data.cameras) {
                this.syncCameras(data.cameras);
            }
        } catch (e) {
            console.warn('⚠️ Error polling cámaras', e);
        }
    }

    async setOnAir(camIndex) {
        const card = document.querySelector(`.camera-card[data-camera="${camIndex}"]`);
        if (card) {
            this.applyState(card, { status: 'on_air' });
        }

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
    // SYNC CAMERAS
    // ============================
    syncCameras(cameras) {
        let onAirCam = null;
        const backendIndexes = new Set(Object.keys(cameras));

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

            if (!wrapper && cam.status !== 'offline') {
                card = this.createCameraCard(index);
            }

            if (!card) return;

            if (this.lastState[index] !== cam.status) {
                this.applyState(card, cam);
                this.lastState[index] = cam.status;
            }

            if (
                (cam.status === 'ready' || cam.status === 'on_air') &&
                cam.hls_url
            ) {
                this.ensureVideoElement(card);
                this.attachStream(card, cam.hls_url);
            }

            if (cam.status === 'on_air') {
                onAirCam = cam;
            }
        });

        this.syncPreview(onAirCam);
    }

    syncPreview(cam) {
        const video = document.getElementById('mainPreviewVideo');
        const empty = document.getElementById('previewEmpty');
        const globalStatus = document.getElementById('globalStatus');

        if (!cam || !cam.hls_url) {
            if (this.hasActivePreview) return;
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
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                video.play().catch(() => {});
            });
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
        if (this.previewHls) {
            this.previewHls.destroy();
            this.previewHls = null;
        }
        this.currentPreviewUrl = null;
        this.hasActivePreview = false;
    }

    createCameraCard(index) {
        const grid = document.getElementById('camerasGrid');
        if (!grid) return null;

        const wrapper = document.createElement('div');
        wrapper.className = 'camera-wrapper';
        wrapper.dataset.camera = index;

        wrapper.innerHTML = `
            <div class="camera-external-toolbar" style="display: none;">
                <button class="tool-btn" data-action="mute">🎤</button>
                <button class="tool-btn" data-action="solo">🎧</button>
                <button class="tool-btn" data-action="stats">📊</button>
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

    bindToolbarEvents(wrapper, index) {
        const btns = wrapper.querySelectorAll('.tool-btn');
        btns.forEach(btn => {
            btn.onclick = async () => {
                const action = btn.dataset.action;

                if (action === 'mute') {
                    const video = wrapper.querySelector('video');
                    if (video) {
                        video.muted = !video.muted;
                        btn.textContent = video.muted ? '🔇' : '🎤';
                    }
                }

                if (action === 'close') {
                    if (confirm(`¿Desconectar cámara ${index}?`)) {
                        await fetch(`/rechazar-camara/${index}/`, {
                            method: 'POST',
                            headers: { 'X-CSRFToken': getCSRFToken() }
                        });
                    }
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

        if (cam.status === 'pending') {
            badge.textContent = 'SOLICITUD';
            if (!preview.querySelector('video')) {
                preview.innerHTML = `<div class="preview-empty">Intento de conexión detectado</div>`;
            }
            bar.classList.remove('hidden-bar');
            actionArea.innerHTML = '';
            this.ensurePendingActions(card);
        }

        if (cam.status === 'ready') {
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

            this.ensureVideoElement(card);
            this.attachStream(card, cam.hls_url);
        }

        if (cam.status === 'on_air') {
            badge.innerHTML = `<span class="badge-pulse"></span> EN AIRE`;
            bar.innerHTML = '';
            bar.classList.add('hidden-bar');
            actionArea.innerHTML = '';
        }
    }

    ensureVideoElement(card) {
        const preview = card.querySelector('.camera-preview');
        if (!preview.querySelector('video')) {
            preview.innerHTML = `<video class="camera-video" autoplay muted playsinline></video>`;
        }
    }

    attachStream(card, url) {
        if (!window.Hls || !Hls.isSupported() || !url) return;
        const video = card.querySelector('video');
        if (!video) return;

        if (video._hls) video._hls.destroy();

        const hls = new Hls({ lowLatencyMode: true });
        hls.loadSource(url);
        hls.attachMedia(video);
        video._hls = hls;
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
        };
    }
}

// ===================================
// UTILS & INIT
// ===================================
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content;
}

document.addEventListener('DOMContentLoaded', () => {
    let cameraPoller = null;

    if (document.querySelector('.control-body')) {
        new ControlPanel();
        cameraPoller = new CameraStatePoller();
    }

    const video = document.getElementById('mainPreviewVideo');
    const stopBtn = document.getElementById('btnStopStream');
    const volume = document.getElementById('previewVolume');

    if (video) {
        volume?.addEventListener('input', () => {
            video.muted = false;
            video.volume = volume.value;
        });

        stopBtn?.addEventListener('click', async () => {
            if (!cameraPoller || !cameraPoller.hasActivePreview) return;

            if (confirm('¿Detener transmisión actual?')) {
                await fetch('/detener-transmision/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCSRFToken() }
                });

                cameraPoller.destroyPreview();

                const empty = document.getElementById('previewEmpty');
                const globalStatus = document.getElementById('globalStatus');

                video.style.display = 'none';
                if (empty) empty.style.display = 'flex';

                if (globalStatus) {
                    globalStatus.className = 'header-status-badge off-air';
                    globalStatus.textContent = 'FUERA DEL AIRE';
                }
            }
        });
    }

    const userInfo = document.getElementById('userInfo');
    const userMenu = document.getElementById('userMenu');
    if (userInfo && userMenu) {
        userInfo.addEventListener('click', e => {
            e.stopPropagation();
            userMenu.style.display =
                userMenu.style.display === 'block' ? 'none' : 'block';
        });
        document.addEventListener('click', () => {
            userMenu.style.display = 'none';
        });
    }
});
