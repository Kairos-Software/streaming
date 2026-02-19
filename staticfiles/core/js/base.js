// ===================================
// CONTROL PANEL GLOBAL
// ===================================
class ControlPanel {
    constructor() {
        console.log('🎛 ControlPanel iniciado');
    }
}

// ===================================
// UTILS (Globales para uso en otras vistas)
// ===================================
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content;
}

// ===================================
// BASE INIT
// ===================================
document.addEventListener('DOMContentLoaded', () => {
    // Inicialización base
    new ControlPanel();

    // ----------------------------
    // USER MENU INTERACTION
    // ----------------------------
    const userInfo = document.getElementById('userInfo');
    const userMenu = document.getElementById('userMenu');

    if (userInfo && userMenu) {
        // Al hacer clic en el nombre/avatar, alterna el menú
        userInfo.addEventListener('click', e => {
            e.stopPropagation(); // Evita que el clic llegue al document y lo cierre inmediatamente
            userMenu.style.display =
                userMenu.style.display === 'block' ? 'none' : 'block';
        });

        // Al hacer clic en cualquier otro lado, cierra el menú
        document.addEventListener('click', () => {
            userMenu.style.display = 'none';
        });
    }
});