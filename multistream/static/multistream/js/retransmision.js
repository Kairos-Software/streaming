// === FUNCIONES PARA RETRANSMISIÓN ===

// Cambiar entre pestañas
function mostrarTab(tab) {
    // Ocultar todas las pestañas
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

    // Mostrar la pestaña seleccionada
    document.getElementById("tab-" + tab).classList.add("active");
    document.querySelector(`.tab-btn[onclick="mostrarTab('${tab}')"]`).classList.add("active");
}

// Copiar texto al portapapeles
function copiarTexto(idInput, boton) {
    const input = document.getElementById(idInput);
    const original = boton.innerHTML;

    navigator.clipboard.writeText(input.value).then(() => {
        boton.classList.add("copied");
        boton.innerHTML = "✓ Copiado";

        setTimeout(() => {
            boton.classList.remove("copied");
            boton.innerHTML = original;
        }, 2000);
    }).catch(err => {
        console.error("Error al copiar: ", err);
    });
}

// Mostrar/ocultar clave de transmisión
function toggleClave(idInput, boton) {
    const input = document.getElementById(idInput);
    const visible = input.type === "text";
    input.type = visible ? "password" : "text";
    boton.innerText = visible ? "Mostrar" : "Ocultar";
}
