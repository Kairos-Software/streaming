// Script general para la página
document.addEventListener("DOMContentLoaded", () => {
    console.log("Frontend cargado con base.js ✅");

    // Animación de bienvenida más elegante
    const title = document.querySelector("h1");
    if (title) {
        title.style.opacity = 0;
        title.style.transform = "translateY(-10px)";
        setTimeout(() => {
            title.style.transition = "opacity 1.5s ease, transform 1.5s ease";
            title.style.opacity = 1;
            title.style.transform = "translateY(0)";
        }, 300);
    }

    // Inicialización de Alpine.js
    document.addEventListener("alpine:init", () => {
        Alpine.data("cameraControl", () => ({
            cam: 1,
            changeCam(num) {
                this.cam = num;
                this.showNotification(`Cámara ${num} activada 🎥`);
            },
            showNotification(msg) {
                const notif = document.createElement("div");
                notif.textContent = msg;
                notif.className = "notification";
                document.body.appendChild(notif);

                // Animación de entrada
                setTimeout(() => notif.classList.add("visible"), 50);

                // Desaparece después de 3s
                setTimeout(() => {
                    notif.classList.remove("visible");
                    setTimeout(() => notif.remove(), 500);
                }, 3000);
            }
        }));
    });
});
