/* =========================================
   KAIRCAM DAW MIXER - PROFESSIONAL
   ========================================= */

const mixer = {
    channels: [],
    selectedChannel: null,
    soloChannel: null,
    masterMuted: false,
    masterVolume: 100,
    playing: false,
    recording: false,
    tempo: 120
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initTransport();
    initMasterStrip();
    startMetering();
    updateStats();
});

// ===== TRANSPORT =====
function initTransport() {
    const btnRecord = document.getElementById('btnRecord');
    const btnPlay = document.getElementById('btnPlay');
    const btnStop = document.getElementById('btnStop');
    const btnLoop = document.getElementById('btnLoop');
    const btnMetronome = document.getElementById('btnMetronome');
    const btnAddChannel = document.getElementById('btnAddChannel');
    
    btnRecord.addEventListener('click', () => {
        mixer.recording = !mixer.recording;
        btnRecord.classList.toggle('active', mixer.recording);
    });
    
    btnPlay.addEventListener('click', () => {
        mixer.playing = !mixer.playing;
        btnPlay.classList.toggle('active', mixer.playing);
        if (mixer.playing) {
            btnStop.classList.remove('active');
        }
    });
    
    btnStop.addEventListener('click', () => {
        mixer.playing = false;
        mixer.recording = false;
        btnPlay.classList.remove('active');
        btnRecord.classList.remove('active');
        btnStop.classList.add('active');
        setTimeout(() => btnStop.classList.remove('active'), 200);
    });
    
    btnLoop.addEventListener('click', () => {
        btnLoop.classList.toggle('active');
    });
    
    btnMetronome.addEventListener('click', () => {
        btnMetronome.classList.toggle('active');
    });
    
    btnAddChannel.addEventListener('click', addChannel);
    
    // Tempo input
    const tempoInput = document.querySelector('.tempo-input');
    tempoInput.addEventListener('change', (e) => {
        mixer.tempo = Math.max(40, Math.min(300, parseInt(e.target.value) || 120));
        e.target.value = mixer.tempo;
    });
}

// ===== MASTER STRIP =====
function initMasterStrip() {
    const fader = document.getElementById('masterFader');
    const volume = document.getElementById('masterVolume');
    const cap = document.getElementById('masterCap');
    const pan = document.getElementById('masterPan');
    const panValue = document.getElementById('masterPanValue');
    const mute = document.getElementById('masterMute');
    const solo = document.getElementById('masterSolo');
    
    // Fader
    fader.addEventListener('input', (e) => {
        mixer.masterVolume = parseInt(e.target.value);
        updateMasterVolume();
        updateFaderCap(cap, mixer.masterVolume);
    });
    
    // Pan
    pan.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        if (value === 0) {
            panValue.textContent = 'C';
        } else if (value < 0) {
            panValue.textContent = `L${Math.abs(value)}`;
        } else {
            panValue.textContent = `R${value}`;
        }
    });
    
    // Mute
    mute.addEventListener('click', () => {
        mixer.masterMuted = !mixer.masterMuted;
        mute.classList.toggle('active', mixer.masterMuted);
    });
    
    // Solo
    solo.addEventListener('click', () => {
        solo.classList.toggle('active');
    });
    
    // Initialize knobs
    initKnobs(document.querySelector('.master'));
    
    // Initialize fader cap
    updateFaderCap(cap, mixer.masterVolume);
}

function updateMasterVolume() {
    const volume = document.getElementById('masterVolume');
    const db = volumeToDb(mixer.masterVolume);
    volume.textContent = `${db} dB`;
}

function updateFaderCap(cap, value) {
    const percentage = (value / 127) * 100;
    cap.style.bottom = `${percentage}%`;
}

// ===== ADD CHANNEL =====
function addChannel() {
    const channelId = mixer.channels.length + 1;
    
    const channel = {
        id: channelId,
        name: `Channel ${channelId}`,
        volume: 100,
        pan: 0,
        muted: false,
        solo: false,
        recording: false,
        meter: 0,
        peak: 0
    };
    
    mixer.channels.push(channel);
    renderChannel(channel);
    updateStats();
}

function renderChannel(channel) {
    const rack = document.getElementById('channelsRack');
    
    const strip = document.createElement('div');
    strip.className = 'channel-strip';
    strip.id = `channel-${channel.id}`;
    
    strip.innerHTML = `
        <div class="strip-header">
            <span class="strip-label">CH ${channel.id}</span>
            <div class="strip-indicator active"></div>
        </div>
        
        <div class="channel-name">
            <svg class="channel-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            </svg>
            <input type="text" class="channel-input" value="${channel.name}">
        </div>
        
        <div class="inserts-section">
            <button class="insert-slot empty" title="Add Insert">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19"/>
                    <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
            </button>
        </div>
        
        <div class="eq-section">
            <div class="eq-header">
                <span class="eq-label">EQ</span>
                <label class="toggle-switch">
                    <input type="checkbox" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="eq-controls">
                <div class="eq-knob">
                    <div class="knob" data-value="0">
                        <div class="knob-indicator"></div>
                    </div>
                    <span class="knob-label">LOW</span>
                    <span class="knob-value">0.0</span>
                </div>
                <div class="eq-knob">
                    <div class="knob" data-value="0">
                        <div class="knob-indicator"></div>
                    </div>
                    <span class="knob-label">MID</span>
                    <span class="knob-value">0.0</span>
                </div>
                <div class="eq-knob">
                    <div class="knob" data-value="0">
                        <div class="knob-indicator"></div>
                    </div>
                    <span class="knob-label">HIGH</span>
                    <span class="knob-value">0.0</span>
                </div>
            </div>
        </div>
        
        <div class="meter-section">
            <div class="stereo-meter">
                <div class="meter-bars">
                    <div class="meter-bar">
                        <div class="meter-fill" id="meter-${channel.id}"></div>
                        <div class="meter-peak" id="peak-${channel.id}"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="pan-section">
            <input type="range" class="pan-slider" min="-100" max="100" value="0" id="pan-${channel.id}">
            <div class="pan-display">
                <span class="pan-label">PAN</span>
                <span class="pan-value" id="panValue-${channel.id}">C</span>
            </div>
        </div>
        
        <div class="fader-section">
            <input type="range" class="fader-slider" min="0" max="127" value="100" orient="vertical" id="fader-${channel.id}">
            <div class="fader-track"></div>
            <div class="fader-cap" id="cap-${channel.id}"></div>
        </div>
        
        <div class="volume-display" id="volume-${channel.id}">0.0 dB</div>
        
        <div class="strip-footer">
            <button class="footer-btn mute" id="mute-${channel.id}">M</button>
            <button class="footer-btn solo" id="solo-${channel.id}">S</button>
            <button class="footer-btn record" id="rec-${channel.id}">R</button>
        </div>
    `;
    
    rack.appendChild(strip);
    
    // Setup channel controls
    setupChannelControls(channel, strip);
    
    // Click to select
    strip.addEventListener('click', () => {
        document.querySelectorAll('.channel-strip').forEach(s => s.classList.remove('selected'));
        strip.classList.add('selected');
        mixer.selectedChannel = channel.id;
    });
}

function setupChannelControls(channel, strip) {
    const fader = strip.querySelector(`#fader-${channel.id}`);
    const volume = strip.querySelector(`#volume-${channel.id}`);
    const cap = strip.querySelector(`#cap-${channel.id}`);
    const pan = strip.querySelector(`#pan-${channel.id}`);
    const panValue = strip.querySelector(`#panValue-${channel.id}`);
    const mute = strip.querySelector(`#mute-${channel.id}`);
    const solo = strip.querySelector(`#solo-${channel.id}`);
    const rec = strip.querySelector(`#rec-${channel.id}`);
    const nameInput = strip.querySelector('.channel-input');
    
    // Fader
    fader.addEventListener('input', (e) => {
        channel.volume = parseInt(e.target.value);
        const db = volumeToDb(channel.volume);
        volume.textContent = `${db} dB`;
        updateFaderCap(cap, channel.volume);
    });
    
    // Pan
    pan.addEventListener('input', (e) => {
        const value = parseInt(e.target.value);
        channel.pan = value;
        if (value === 0) {
            panValue.textContent = 'C';
        } else if (value < 0) {
            panValue.textContent = `L${Math.abs(value)}`;
        } else {
            panValue.textContent = `R${value}`;
        }
    });
    
    // Mute
    mute.addEventListener('click', () => {
        channel.muted = !channel.muted;
        mute.classList.toggle('active', channel.muted);
    });
    
    // Solo
    solo.addEventListener('click', () => {
        channel.solo = !channel.solo;
        solo.classList.toggle('active', channel.solo);
        handleSolo();
    });
    
    // Record
    rec.addEventListener('click', () => {
        channel.recording = !channel.recording;
        rec.classList.toggle('active', channel.recording);
    });
    
    // Name
    nameInput.addEventListener('change', (e) => {
        channel.name = e.target.value;
    });
    
    // Initialize
    updateFaderCap(cap, channel.volume);
    initKnobs(strip);
}

// ===== KNOBS =====
function initKnobs(container) {
    const knobs = container.querySelectorAll('.knob');
    
    knobs.forEach(knob => {
        let isDragging = false;
        let startY = 0;
        let startValue = 0;
        
        knob.addEventListener('mousedown', (e) => {
            isDragging = true;
            startY = e.clientY;
            startValue = parseFloat(knob.dataset.value) || 0;
            document.body.style.cursor = 'ns-resize';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            
            const delta = (startY - e.clientY) * 0.1;
            let newValue = startValue + delta;
            newValue = Math.max(-12, Math.min(12, newValue));
            
            knob.dataset.value = newValue;
            updateKnobRotation(knob, newValue);
            
            const valueDisplay = knob.parentElement.querySelector('.knob-value');
            if (valueDisplay) {
                valueDisplay.textContent = newValue >= 0 ? `+${newValue.toFixed(1)}` : newValue.toFixed(1);
            }
        });
        
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                document.body.style.cursor = '';
            }
        });
    });
}

function updateKnobRotation(knob, value) {
    const indicator = knob.querySelector('.knob-indicator');
    const rotation = (value / 12) * 135; // -135 to +135 degrees
    indicator.style.transform = `translateX(-50%) rotate(${rotation}deg)`;
    indicator.style.transformOrigin = 'center bottom';
}

// ===== SOLO HANDLING =====
function handleSolo() {
    const hasSolo = mixer.channels.some(ch => ch.solo);
    mixer.soloChannel = hasSolo ? mixer.channels.find(ch => ch.solo)?.id : null;
}

// ===== METERING =====
function startMetering() {
    setInterval(() => {
        // Master meters
        if (!mixer.masterMuted) {
            const level = Math.random() * 0.6 + 0.2;
            updateMeter('masterMeterL', 'masterPeakL', level);
            updateMeter('masterMeterR', 'masterPeakR', level * 0.95);
        } else {
            updateMeter('masterMeterL', 'masterPeakL', 0);
            updateMeter('masterMeterR', 'masterPeakR', 0);
        }
        
        // Channel meters
        mixer.channels.forEach(channel => {
            if (!channel.muted && (mixer.soloChannel === null || channel.solo)) {
                const level = Math.random() * 0.5 + 0.3;
                channel.meter = level;
                if (level > channel.peak) {
                    channel.peak = level;
                } else {
                    channel.peak *= 0.95;
                }
            } else {
                channel.meter = 0;
                channel.peak *= 0.9;
            }
            
            const meterEl = document.getElementById(`meter-${channel.id}`);
            const peakEl = document.getElementById(`peak-${channel.id}`);
            
            if (meterEl) {
                meterEl.style.height = `${channel.meter * 100}%`;
            }
            
            if (peakEl) {
                peakEl.style.top = `${(1 - channel.peak) * 100}%`;
            }
        });
        
        // Update CPU
        updateCPU();
        
    }, 50);
}

function updateMeter(meterId, peakId, level) {
    const meter = document.getElementById(meterId);
    const peak = document.getElementById(peakId);
    
    if (meter) {
        meter.style.height = `${level * 100}%`;
    }
    if (peak) {
        peak.style.top = `${(1 - level) * 100}%`;
    }
}

// ===== UTILITIES =====
function volumeToDb(volume) {
    if (volume === 0) return '-∞';
    // 0-127 to dB scale (-60 to +6)
    const normalized = volume / 127;
    const db = 20 * Math.log10(normalized);
    return db >= 0 ? `+${db.toFixed(1)}` : db.toFixed(1);
}

function updateStats() {
    document.getElementById('statChannels').textContent = mixer.channels.length;
}

function updateCPU() {
    const cpu = Math.random() * 10 + 8;
    document.getElementById('statCpu').textContent = `${cpu.toFixed(0)}%`;
}

// Initialize with 4 channels
setTimeout(() => {
    for (let i = 0; i < 4; i++) {
        addChannel();
    }
}, 100);

console.log('🎛️ DAW Mixer Ready');