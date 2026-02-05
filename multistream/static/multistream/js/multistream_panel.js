// ===================================
// MULTISTREAM PANEL MANAGER V2
// Gestión completa de retransmisión con persistencia
// ===================================

class MultistreamManager {
  constructor() {
    this.activePlatforms = {};
    this.init();
  }

  async init() {
    console.log('🎛 MultistreamManager V2 iniciado');
    
    // 1. Cargar estado guardado localmente
    this.loadLocalState();
    
    // 2. Sincronizar con el servidor
    await this.syncWithServer();
    
    // 3. Configurar eventos
    this.bindEvents();
    this.checkStreamStatus();
    
    // 4. Escuchar actualizaciones por WebSocket
    this.listenToWebSocket();
    
    console.log('✅ MultistreamManager inicializado completamente');
  }

  // ========================================
  // PERSISTENCIA Y SINCRONIZACIÓN
  // ========================================

  /**
   * Carga el estado guardado en localStorage
   */
  loadLocalState() {
    try {
      const saved = localStorage.getItem('multistream_active_platforms');
      if (saved) {
        this.activePlatforms = JSON.parse(saved);
        console.log('📦 Estado local cargado:', this.activePlatforms);
        this.updateRestreamStatus();
      }
    } catch (error) {
      console.error('❌ Error cargando estado local:', error);
    }
  }

  /**
   * Guarda el estado actual en localStorage
   */
  saveLocalState() {
    try {
      localStorage.setItem('multistream_active_platforms', JSON.stringify(this.activePlatforms));
      console.log('💾 Estado guardado localmente');
    } catch (error) {
      console.error('❌ Error guardando estado local:', error);
    }
  }

  /**
   * Sincroniza con el servidor para obtener el estado real
   */
  async syncWithServer() {
    try {
      console.log('🔄 Sincronizando con servidor...');
      
      const response = await fetch('/multistream/api/restream/status/', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        cache: 'no-store'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('📥 Estado del servidor:', data);

      if (data.ok && data.active_platforms) {
        // Actualizar estado con datos del servidor
        this.activePlatforms = {};
        
        data.active_platforms.forEach(platform => {
          this.activePlatforms[platform] = {
            status: 'streaming',
            startedAt: Date.now(),
            syncedFromServer: true
          };
        });

        this.saveLocalState();
        this.updateRestreamStatus();
        
        console.log('✅ Estado sincronizado:', Object.keys(this.activePlatforms));
      }

    } catch (error) {
      console.warn('⚠️ No se pudo sincronizar con servidor:', error.message);
      console.log('📦 Usando estado local guardado');
    }
  }

  /**
   * Escucha eventos de WebSocket para actualizaciones en tiempo real
   */
  listenToWebSocket() {
    // Buscar el WebSocket ya existente o esperar a que se cree
    const checkWebSocket = () => {
      // El WebSocket se crea en home.js como variable global
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
      
      // Si ya existe un WebSocket global, usarlo
      if (window.panelWebSocket) {
        this.attachWebSocketListeners(window.panelWebSocket);
        return;
      }

      // Sino, crear uno nuevo o esperar
      setTimeout(checkWebSocket, 500);
    };

    checkWebSocket();
  }

  /**
   * Adjunta listeners al WebSocket para eventos de retransmisión
   */
  attachWebSocketListeners(ws) {
    console.log('🔌 WebSocket conectado a MultistreamManager');

    const originalOnMessage = ws.onmessage;

    ws.onmessage = (event) => {
      // Llamar al handler original primero
      if (originalOnMessage) {
        originalOnMessage.call(ws, event);
      }

      // Procesar mensajes de retransmisión
      try {
        const data = JSON.parse(event.data);

        if (data.tipo === 'restream_update') {
          console.log('📡 Actualización de retransmisión:', data);
          this.handleRestreamUpdate(data);
        }
      } catch (error) {
        // Ignorar errores de parsing si no es JSON
      }
    };
  }

  /**
   * Maneja actualizaciones de retransmisión desde WebSocket
   */
  handleRestreamUpdate(data) {
    const { platform, action, status } = data;

    switch (action) {
      case 'started':
        this.addActivePlatform(platform);
        break;

      case 'stopped':
        this.removePlatform(platform);
        break;

      case 'error':
        this.updatePlatformStatus(platform, 'error');
        break;

      case 'status_update':
        this.updatePlatformStatus(platform, status);
        break;
    }
  }

  // ========================================
  // GESTIÓN DE ESTADO DE STREAM
  // ========================================

  checkStreamStatus() {
    // Observar cambios en el estado del stream
    const observer = new MutationObserver(() => {
      this.updateRestreamButtonVisibility();
    });

    const liveBadge = document.getElementById('liveBadge');
    if (liveBadge) {
      observer.observe(liveBadge, { 
        attributes: true, 
        attributeFilter: ['class'] 
      });
    }

    // También verificar el estado inicial después de un breve delay
    setTimeout(() => {
      this.updateRestreamButtonVisibility();
    }, 500);
  }

  updateRestreamButtonVisibility() {
    const liveBadge = document.getElementById('liveBadge');
    const btnRestream = document.getElementById('btnRestream');
    
    if (liveBadge && btnRestream) {
      const isLive = liveBadge.classList.contains('active');
      btnRestream.style.display = isLive ? 'flex' : 'none';
      
      if (isLive) {
        console.log('🔴 Stream en vivo detectado - Botón Retransmitir visible');
      }
    }
  }

  // ========================================
  // EVENTOS DEL MODAL
  // ========================================

  bindEvents() {
    const btnRestream = document.getElementById('btnRestream');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCancelRestream = document.getElementById('btnCancelRestream');
    const btnStartRestream = document.getElementById('btnStartRestream');
    const restreamModal = document.getElementById('restreamModal');

    if (btnRestream) {
      btnRestream.addEventListener('click', () => {
        this.openModal();
      });
    }

    if (btnCloseModal) {
      btnCloseModal.addEventListener('click', () => {
        this.closeModal();
      });
    }

    if (btnCancelRestream) {
      btnCancelRestream.addEventListener('click', () => {
        this.closeModal();
      });
    }

    if (restreamModal) {
      restreamModal.addEventListener('click', (e) => {
        if (e.target.classList.contains('restream-modal-overlay') || e.target === restreamModal) {
          this.closeModal();
        }
      });
    }

    if (btnStartRestream) {
      btnStartRestream.addEventListener('click', () => {
        this.startRestream();
      });
    }
  }

  openModal() {
    const restreamModal = document.getElementById('restreamModal');
    if (restreamModal) {
      restreamModal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  closeModal() {
    const restreamModal = document.getElementById('restreamModal');
    if (restreamModal) {
      restreamModal.style.display = 'none';
      document.body.style.overflow = 'auto';
    }
  }

  // ========================================
  // INICIAR RETRANSMISIÓN
  // ========================================

  async startRestream(force = false) {
    const selectedPlatforms = Array.from(
      document.querySelectorAll('input[name="platform"]:checked')
    ).map(input => input.value);

    if (selectedPlatforms.length === 0) {
      alert('Por favor selecciona al menos una plataforma');
      return;
    }

    console.log(`🚀 Iniciando retransmisión en: ${selectedPlatforms.join(', ')} (force=${force})`);
    
    const csrfToken = this.getCSRFToken();
    
    const btnStartRestream = document.getElementById('btnStartRestream');
    btnStartRestream.disabled = true;
    const originalHTML = btnStartRestream.innerHTML;
    btnStartRestream.innerHTML = '<span>Iniciando...</span>';

    try {
      const response = await fetch('/multistream/api/restream/start/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ 
          platforms: selectedPlatforms,
          force: force
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('❌ Error del servidor:', errorText);
        throw new Error(`Error HTTP ${response.status}`);
      }

      const data = await response.json();
      console.log('✅ Respuesta:', data);

      // Verificar si alguna plataforma requiere confirmación
      const requiresConfirmation = data.resultados?.some(r => r.requires_confirmation);

      if (requiresConfirmation && !force) {
        const confirmationMessages = data.resultados
          .filter(r => r.requires_confirmation)
          .map(r => `• ${r.platform.toUpperCase()}: ${r.message}`)
          .join('\n\n');

        const userConfirmed = confirm(
          `⚠️ ADVERTENCIA\n\n${confirmationMessages}\n\n` +
          `Esto detendrá la transmisión actual y comenzará una nueva.\n\n` +
          `¿Deseas continuar?`
        );

        if (userConfirmed) {
          await this.startRestream(true);
          return;
        } else {
          alert('❌ Operación cancelada');
          return;
        }
      }

      if (data.ok) {
        let exitosas = [];
        let fallidas = [];

        data.resultados.forEach(resultado => {
          if (resultado.success) {
            exitosas.push(resultado.platform);
            this.addActivePlatform(resultado.platform);
          } else if (!resultado.requires_confirmation) {
            fallidas.push(`${resultado.platform}: ${resultado.message}`);
          }
        });

        if (exitosas.length > 0) {
          alert(`✅ Retransmisión iniciada en: ${exitosas.join(', ')}`);
        }

        if (fallidas.length > 0) {
          alert(`⚠️ Errores:\n${fallidas.join('\n')}`);
        }

        this.closeModal();
      } else {
        throw new Error(data.error || 'Error desconocido');
      }

    } catch (error) {
      console.error('💥 Error:', error);
      alert(`❌ Error: ${error.message}`);
    } finally {
      btnStartRestream.disabled = false;
      btnStartRestream.innerHTML = originalHTML;
    }
  }

  // ========================================
  // GESTIÓN DE PLATAFORMAS ACTIVAS
  // ========================================

  addActivePlatform(platform) {
    this.activePlatforms[platform] = {
      status: 'streaming',
      startedAt: Date.now()
    };
    
    this.saveLocalState();
    this.updateRestreamStatus();
    this.showRestreamButton();
    
    console.log(`✅ Plataforma activa agregada: ${platform}`);
  }

  removePlatform(platform) {
    delete this.activePlatforms[platform];
    
    this.saveLocalState();
    this.updateRestreamStatus();
    
    console.log(`🗑️ Plataforma removida: ${platform}`);
  }

  updatePlatformStatus(platform, status) {
    if (this.activePlatforms[platform]) {
      this.activePlatforms[platform].status = status;
      
      this.saveLocalState();
      this.updateRestreamStatus();
      
      console.log(`🔄 Estado actualizado: ${platform} -> ${status}`);
    }
  }

  showRestreamButton() {
    const btnRestream = document.getElementById('btnRestream');
    if (btnRestream) {
      btnRestream.style.display = 'flex';
    }
  }

  hideRestreamButton() {
    const btnRestream = document.getElementById('btnRestream');
    if (btnRestream) {
      btnRestream.style.display = 'none';
    }
  }

  // ========================================
  // UI DE RETRANSMISIÓN ACTIVA
  // ========================================

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

    console.log(`🎯 Panel actualizado: ${activePlatformsList.length} plataformas activas`);
  }

  // ========================================
  // DETENER RETRANSMISIÓN
  // ========================================

  async stopPlatformRestream(platform) {
    try {
      console.log(`🛑 Deteniendo ${platform}...`);
      
      const response = await fetch(`/multistream/api/restream/stop/${platform}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        }
      });

      const data = await response.json();

      if (data.ok) {
        console.log(`✅ ${platform} detenido correctamente`);
        this.removePlatform(platform);
        alert(`✅ Retransmisión en ${platform} detenida`);
      } else {
        throw new Error(data.message || 'Error desconocido');
      }

    } catch (error) {
      console.error(`❌ Error deteniendo ${platform}:`, error);
      alert(`Error al detener ${platform}: ${error.message}`);
      this.updatePlatformStatus(platform, 'error');
    }
  }

  // ========================================
  // UTILIDADES
  // ========================================

  getCSRFToken() {
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1];
    return cookieValue;
  }
}

// ========================================
// INICIALIZACIÓN
// ========================================
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('.control-body')) {
    window.multistreamManager = new MultistreamManager();
    console.log('✅ MultistreamManager disponible globalmente');
  }
});