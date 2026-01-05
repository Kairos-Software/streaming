// ===================================
// CONTROL PANEL
// ===================================
class ControlPanel {
    constructor() {
        console.log('🎛 ControlPanel iniciado');
    }
}

// ===================================
// UTILS
// ===================================
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content;
}

// ===================================
// BASE INIT (SOLO GLOBAL)
// ===================================
document.addEventListener('DOMContentLoaded', () => {

    // Inicialización base (siempre)
    new ControlPanel();

    // ----------------------------
    // USER MENU
    // ----------------------------
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
