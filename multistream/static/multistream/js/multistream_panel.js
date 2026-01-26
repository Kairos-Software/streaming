// ===================================
// MULTISTREAM PANEL MANAGER
// Gestión completa de retransmisión
// ===================================

class MultistreamManager {
  constructor() {
    this.activePlatforms = {};
    this.init();
  }

  init() {
    console.log('🎛 MultistreamManager iniciado');
    this.bindEvents();
    this.checkStreamStatus();
  }

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
    console.log('🔑 CSRF Token:', csrfToken ? 'OK' : '❌ NO ENCONTRADO');
    
    const btnStartRestream = document.getElementById('btnStartRestream');
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
        body: JSON.stringify({ 
          platforms: selectedPlatforms,
          force: force  // Nuevo parámetro
        })
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
          console.log(`   [${i}] Requires Confirmation: ${r.requires_confirmation}`);
        });
      }

      // Verificar si alguna plataforma requiere confirmación
      const requiresConfirmation = data.resultados.some(r => r.requires_confirmation);

      if (requiresConfirmation && !force) {
        // Mostrar confirmación al usuario
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
          console.log('✅ Usuario confirmó - reintentando con force=true');
          // Reintentar con force=true
          await this.startRestream(true);
          return;
        } else {
          console.log('❌ Usuario canceló');
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
      alert(`❌ Error: ${error.message}\n\nRevisa la consola (F12)`);
    } finally {
      btnStartRestream.disabled = false;
      btnStartRestream.innerHTML = originalHTML;
    }
  }

  getCSRFToken() {
    const cookieValue = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='))
      ?.split('=')[1];
    return cookieValue;
  }

  addActivePlatform(platform) {
    this.activePlatforms[platform] = {
      status: 'streaming',
      startedAt: Date.now()
    };
    this.updateRestreamStatus();
    this.showRestreamButton();
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
          'X-CSRFToken': this.getCSRFToken()
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

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  if (document.querySelector('.control-body')) {
    window.multistreamManager = new MultistreamManager();
  }
});