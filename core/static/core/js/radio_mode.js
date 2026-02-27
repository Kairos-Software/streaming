(function () {
  "use strict";

  const URLS = {
    activar:    "/radio/activar/",
    desactivar: "/radio/desactivar/",
  };

  const btn     = document.getElementById("btnRadioMode");
  const btnText = document.getElementById("btnRadioText");

  let modoRadioActivo = false;

  function getCsrf() {
    return document.querySelector('meta[name="csrf-token"]')?.content || "";
  }

  function actualizarBoton() {
    if (!btn) return;

    const liveBadge = document.getElementById("liveBadge");
    const enVivo = liveBadge ? liveBadge.classList.contains("active") : false;

    if (!enVivo) {
      btn.style.display = "none";
      return;
    }

    btn.style.display = "inline-flex";

    if (modoRadioActivo) {
      btn.classList.add("btn-radio-activo");
      btnText.textContent = "Volver a Video";
    } else {
      btn.classList.remove("btn-radio-activo");
      btnText.textContent = "Modo Radio";
    }
  }

  async function toggleModoRadio() {
    btn.disabled = true;
    const oldText = btnText.textContent;
    btnText.textContent = "Cambiando...";
    const url = modoRadioActivo ? URLS.desactivar : URLS.activar;
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrf(),
          "Content-Type": "application/json",
        },
      });
      const data = await res.json();
      if (!data.ok) {
        alert("Error: " + (data.error || "Error desconocido"));
        btnText.textContent = oldText;
      }
    } catch (err) {
      alert("Error de red al cambiar modo radio");
      btnText.textContent = oldText;
    } finally {
      btn.disabled = false;
    }
  }

  // Escucha cambios de modo radio por WebSocket
  document.addEventListener("ws:mensaje", function (e) {
    const msg = e.detail;
    if (msg.tipo === "modo_radio_cambio") {
      modoRadioActivo = msg.modo_radio;
      actualizarBoton();
    }
  });

  // Observa el liveBadge igual que multistream_panel.js
  // Cuando cambia a "active" (EN VIVO) o deja de serlo, actualiza el botón
  function iniciarObservador() {
    const liveBadge = document.getElementById("liveBadge");
    if (!liveBadge) return;

    const observer = new MutationObserver(() => {
      actualizarBoton();
    });

    observer.observe(liveBadge, {
      attributes: true,
      attributeFilter: ["class"]
    });
  }

  if (btn) {
    btn.addEventListener("click", toggleModoRadio);
    iniciarObservador();
    // Estado inicial
    setTimeout(actualizarBoton, 500);
  }

})();