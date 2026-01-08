// ==========================================
// KAIRCAM AUDIO ENGINE (Web Audio API)
// ==========================================

class AudioMixer {
    constructor() {
        this.ctx = null; // AudioContext
        this.masterGain = null;
        this.channels = {
            1: { source: null, gain: null, analyser: null, mute: false, solo: false },
            2: { source: null, gain: null, analyser: null, mute: false, solo: false },
            3: { source: null, gain: null, analyser: null, mute: false, solo: false },
            'master': { gain: null, analyser: null } // Master Channel
        };
        this.isStarted = false;
    }

    async init() {
        if (this.isStarted) return;

        try {
            // 1. Crear Contexto de Audio
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AudioContext();
            
            // 2. Crear Canal Master
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = 1.0;
            
            // Analizador para el Master VU
            const masterAnalyser = this.ctx.createAnalyser();
            masterAnalyser.fftSize = 64;
            this.masterGain.connect(masterAnalyser);
            masterAnalyser.connect(this.ctx.destination); // Salida a altavoces/stream
            
            this.channels['master'].gain = this.masterGain;
            this.channels['master'].analyser = masterAnalyser;

            // 3. Inicializar Canales individuales
            [1, 2, 3].forEach(id => this.initChannelNode(id));

            // 4. Listar Dispositivos
            await this.populateDevices();

            // 5. Iniciar Loop de Animación
            this.renderLoop();

            this.isStarted = true;
            this.updateUIStatus(true);
            console.log("🔊 Motor de Audio Iniciado");

        } catch (e) {
            console.error("Error iniciando audio:", e);
            alert("No se pudo acceder al audio. Revisa permisos de micrófono.");
        }
    }

    initChannelNode(id) {
        // Nodos internos del canal (Gain -> Analyser -> Master)
        const gainNode = this.ctx.createGain();
        const analyser = this.ctx.createAnalyser();
        analyser.fftSize = 64;

        gainNode.connect(analyser);
        analyser.connect(this.masterGain); // Mezcla al master

        // Estado inicial
        gainNode.gain.value = 1.0; // Fader al 100% por defecto

        this.channels[id].gain = gainNode;
        this.channels[id].analyser = analyser;
    }

    async populateDevices() {
        const selects = document.querySelectorAll('.device-select');
        
        try {
            // Pedir permiso temporal para leer etiquetas de dispositivos
            await navigator.mediaDevices.getUserMedia({ audio: true });
            
            const devices = await navigator.mediaDevices.enumerateDevices();
            const audioInputs = devices.filter(d => d.kind === 'audioinput');

            selects.forEach(select => {
                // Limpiar opciones (excepto la primera)
                while (select.options.length > 1) select.remove(1);

                audioInputs.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.deviceId;
                    option.text = device.label || `Micrófono ${select.length}`;
                    select.appendChild(option);
                });

                // Evento de cambio
                select.onchange = (e) => {
                    const channelId = e.target.closest('.channel-strip').dataset.channel;
                    this.connectInputToChannel(channelId, e.target.value);
                };
            });

        } catch (e) {
            console.warn("No se pudieron listar dispositivos", e);
        }
    }

    async connectInputToChannel(id, deviceId) {
        const ch = this.channels[id];

        // 1. Desconectar fuente anterior si existe
        if (ch.source) {
            ch.source.disconnect();
            ch.source = null;
        }

        if (!deviceId) return; // Si eligió "Sin Entrada"

        try {
            // 2. Capturar Micrófono Real
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: { 
                    deviceId: { exact: deviceId },
                    echoCancellation: false, // Modo "Pro" sin filtros
                    autoGainControl: false,
                    noiseSuppression: false
                }
            });

            // 3. Crear Fuente y conectar al Gain del canal
            const source = this.ctx.createMediaStreamSource(stream);
            source.connect(ch.gain);
            ch.source = source;
            console.log(`🎤 Canal ${id} conectado a: ${stream.getAudioTracks()[0].label}`);

        } catch (e) {
            console.error(`Error conectando canal ${id}:`, e);
        }
    }

    setVolume(id, value) { // Value 0-120
        const ch = this.channels[id];
        if (!ch || !ch.gain) return;

        // Logarítmico simulado para que se sienta natural
        // 100 en el slider = 1.0 ganancia (0dB)
        const gainVal = value / 100; 
        
        // Si está muteado, guardamos el valor pero no lo aplicamos al nodo
        if (!ch.mute) {
            ch.gain.gain.setTargetAtTime(gainVal, this.ctx.currentTime, 0.05);
        }
        
        // Guardar referencia del nivel físico del fader
        ch.faderLevel = gainVal; 
        
        // Actualizar UI dB
        this.updateDbDisplay(id, value);
    }

    toggleMute(id) {
        const ch = this.channels[id];
        ch.mute = !ch.mute;
        
        // Aplicar Mute Real
        const targetGain = ch.mute ? 0 : (ch.faderLevel || 1);
        ch.gain.gain.setTargetAtTime(targetGain, this.ctx.currentTime, 0.05);

        // UI
        const btn = document.querySelector(`.channel-strip[data-channel="${id}"] .btn-mute`);
        if(btn) btn.classList.toggle('active', ch.mute);
    }

    toggleSolo(id) {
        // Lógica simple de Solo (Silencia visualmente los demás por ahora)
        // Implementar un bus "Solo" real requiere routing más complejo (PFL)
        const btn = document.querySelector(`.channel-strip[data-channel="${id}"] .btn-solo`);
        if(btn) btn.classList.toggle('active');
        console.log("Solo no implementado en routing real todavía");
    }

    updateDbDisplay(id, val) {
        const display = document.querySelector(`.channel-strip[data-channel="${id}"] .db-value`);
        if (!display) return;

        let text = "-inf";
        if (val > 0) {
            // Conversión aproximada Fader -> dB
            const db = 20 * Math.log10(val / 100);
            text = db.toFixed(1);
            if (val == 100) text = "0.0";
            else if (db > 0) text = "+" + text;
        }
        
        display.textContent = text;
        display.style.color = val > 100 ? 'var(--brand-red)' : 'var(--status-ready)';
    }

    renderLoop() {
        if (!this.isStarted) return;

        const dataArray = new Uint8Array(64); // Buffer pequeño para rapidez

        // Loop por canales + Master
        ['1', '2', '3', 'master'].forEach(id => {
            const ch = this.channels[id];
            if (!ch || !ch.analyser) return;

            // Obtener datos de audio en tiempo real
            ch.analyser.getByteFrequencyData(dataArray);

            // Calcular volumen promedio (RMS simple)
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
            const average = sum / dataArray.length;

            // Escalar 0-255 a Porcentaje 0-100 para el CSS
            // Multiplicamos por 1.5 para darle más sensibilidad visual
            let percent = Math.min(100, (average / 255) * 100 * 1.5);

            // Si es mute, forzar 0
            if (ch.mute) percent = 0;

            // Actualizar Vúmetros UI
            const suffix = id === 'master' ? 'm' : id;
            const vuL = document.getElementById(`vu-${suffix}-l`);
            const vuR = document.getElementById(`vu-${suffix}-r`);

            if (vuL) vuL.style.height = `${percent}%`;
            // Simular stereo (pequeña variación)
            if (vuR) vuR.style.height = `${Math.max(0, percent * 0.95)}%`;
        });

        requestAnimationFrame(() => this.renderLoop());
    }

    updateUIStatus(active) {
        const btn = document.getElementById('btnStartEngine');
        const text = btn.querySelector('span'); // LED
        if (active) {
            btn.classList.add('active');
            btn.innerHTML = `<span class="status-led"></span> MOTOR ACTIVO`;
        }
    }
}

// ==========================================
// INICIALIZACIÓN Y EVENTOS
// ==========================================
const mixer = new AudioMixer();

document.addEventListener('DOMContentLoaded', () => {
    
    // Botón Inicio
    document.getElementById('btnStartEngine').addEventListener('click', () => {
        mixer.init();
    });

    // Faders de Volumen
    document.querySelectorAll('.vol-fader').forEach(fader => {
        fader.addEventListener('input', (e) => {
            const id = e.target.closest('.channel-strip').dataset.channel;
            mixer.setVolume(id, e.target.value);
        });
    });

    // Exponer mixer global para los botones onclick del HTML
    window.mixer = mixer;
});