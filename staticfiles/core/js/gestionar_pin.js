document.addEventListener("DOMContentLoaded", () => {

    /* ======================================================
       ELEMENTOS
       ====================================================== */

    const pinDisplaySection = document.getElementById("pinDisplaySection");
    const pinFormSection = document.getElementById("pinFormSection");

    const btnEditarPin = document.getElementById("btnEditarPin");
    const btnEstablecerPin = document.getElementById("btnEstablecerPin");
    const btnCancelarEdicion = document.getElementById("btnCancelarEdicion");

    const btnTogglePin = document.getElementById("btnTogglePin");
    const pinMasked = document.getElementById("pinMasked");
    const pinReal = document.getElementById("pinReal");

    const toggleInputPinBtn = document.getElementById("togglePinVisibility");
    const pinInput = document.querySelector(".pin-field-container input");

    /* ======================================================
       MOSTRAR / OCULTAR FORMULARIO
       ====================================================== */

    function mostrarFormulario() {
        if (pinFormSection) pinFormSection.classList.remove("hidden");
        if (pinDisplaySection) pinDisplaySection.classList.add("hidden");
    }

    function ocultarFormulario() {
        if (pinFormSection) pinFormSection.classList.add("hidden");
        if (pinDisplaySection) pinDisplaySection.classList.remove("hidden");
    }

    if (btnEditarPin) {
        btnEditarPin.addEventListener("click", mostrarFormulario);
    }

    if (btnEstablecerPin) {
        btnEstablecerPin.addEventListener("click", mostrarFormulario);
    }

    if (btnCancelarEdicion) {
        btnCancelarEdicion.addEventListener("click", ocultarFormulario);
    }

    /* ======================================================
       MOSTRAR / OCULTAR PIN ACTUAL (DB)
       ====================================================== */

    if (btnTogglePin && pinMasked && pinReal) {
        let visible = false;

        btnTogglePin.addEventListener("click", () => {
            visible = !visible;

            if (visible) {
                pinMasked.classList.add("hidden");
                pinReal.classList.remove("hidden");
                btnTogglePin.textContent = "Ocultar PIN";
            } else {
                pinMasked.classList.remove("hidden");
                pinReal.classList.add("hidden");
                btnTogglePin.textContent = "Mostrar PIN";
            }
        });
    }

    /* ======================================================
       MOSTRAR / OCULTAR PIN EN INPUT
       ====================================================== */

    if (toggleInputPinBtn && pinInput) {
        toggleInputPinBtn.addEventListener("click", () => {
            const isPassword = pinInput.type === "password";

            pinInput.type = isPassword ? "text" : "password";
            toggleInputPinBtn.innerHTML = isPassword
                ? '<i class="fas fa-eye-slash"></i>'
                : '<i class="fas fa-eye"></i>';
        });
    }

});
