// ============================================
// RETRANSMISIÓN - GESTIÓN DE PLATAFORMAS
// ============================================

/**
 * Cambia la plataforma mostrada
 * @param {string} platform - Nombre de la plataforma (youtube, facebook, twitch, etc.)
 */
function cambiarPlataforma(platform) {
    // Ocultar todas las secciones
    const sections = document.querySelectorAll('.platform-section');
    sections.forEach(section => {
        section.classList.remove('active');
    });
    
    // Mostrar la sección seleccionada
    const targetSection = document.getElementById(`content-${platform}`);
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    // Guardar preferencia en localStorage (opcional)
    localStorage.setItem('selected_platform', platform);
}

/**
 * Copia texto al portapapeles
 * @param {string} inputId - ID del input a copiar
 * @param {HTMLElement} button - Botón que disparó la acción
 */
function copiarTexto(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    const originalText = button.innerHTML;

    // Copiar al portapapeles
    navigator.clipboard.writeText(input.value)
        .then(() => {
            // Feedback visual
            button.classList.add('copied');
            button.innerHTML = '✓ Copiado';

            // Restaurar después de 2 segundos
            setTimeout(() => {
                button.classList.remove('copied');
                button.innerHTML = originalText;
            }, 2000);
        })
        .catch(err => {
            console.error('Error al copiar:', err);
            button.innerHTML = '❌ Error';
            setTimeout(() => {
                button.innerHTML = originalText;
            }, 2000);
        });
}

/**
 * Alterna visibilidad de la clave de transmisión
 * @param {string} inputId - ID del input password
 * @param {HTMLElement} button - Botón que disparó la acción
 */
function toggleClave(inputId, button) {
    const input = document.getElementById(inputId);
    if (!input) return;
    
    const isPassword = input.type === 'password';
    
    // Cambiar tipo de input
    input.type = isPassword ? 'text' : 'password';
    
    // Actualizar texto del botón
    button.innerHTML = isPassword ? '🙈 Ocultar' : '👁️ Mostrar';
}

/**
 * Restaura la última plataforma seleccionada al cargar la página
 */
function restaurarPlataforma() {
    const saved = localStorage.getItem('selected_platform');
    if (saved && saved !== 'youtube') {
        const select = document.getElementById('platform-select');
        if (select) {
            select.value = saved;
            cambiarPlataforma(saved);
        }
    }
}

// Inicializar al cargar la página
document.addEventListener('DOMContentLoaded', () => {
    // Restaurar selección si existe (opcional - comentá si no querés esta funcionalidad)
    // restaurarPlataforma();
    
    console.log('✓ Sistema de retransmisión cargado correctamente');
});