(function () {
  "use strict";

  // ══════════════════════════════════════════════
  // MODO RADIO - TOGGLE
  // ══════════════════════════════════════════════

  const URLS = {
    activar:         "/radio/activar/",
    desactivar:      "/radio/desactivar/",
    imagenEstado:    "/radio/imagen/estado/",
    imagenSubir:     "/radio/imagen/subir/",
    imagenEliminar:  "/radio/imagen/eliminar/",
  };

  const btn     = document.getElementById("btnRadioMode");
  const btnText = document.getElementById("btnRadioText");

  let modoRadioActivo = false;

  function getCsrf() {
    return document.querySelector('meta[name="csrf-token"]')?.content
        || document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || "";
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
    setTimeout(actualizarBoton, 500);
  }


  // ══════════════════════════════════════════════
  // IMAGEN DE RADIO - GESTIÓN EN AJUSTES/PERFIL
  // ══════════════════════════════════════════════

  const inputFile      = document.getElementById("inputImagenRadio");
  const btnSeleccionar = document.getElementById("btnSeleccionarImagenRadio");
  const btnSubir       = document.getElementById("btnSubirImagenRadio");
  const btnEliminar    = document.getElementById("btnEliminarImagenRadio");
  const fileName       = document.getElementById("radioImageFileName");
  const preview        = document.getElementById("radioImagePreview");
  const thumb          = document.getElementById("radioImageThumb");
  const empty          = document.getElementById("radioImageEmpty");
  const msg            = document.getElementById("radioImageMsg");

  // Solo ejecutar si estamos en la página de perfil
  if (inputFile) {

    // Cargar estado inicial
    fetch(URLS.imagenEstado)
      .then(r => r.json())
      .then(data => {
        if (data.tiene_imagen) {
          thumb.src = data.url_preview + "?t=" + Date.now();
          preview.style.display = "block";
          empty.style.display = "none";
        } else {
          preview.style.display = "none";
          empty.style.display = "block";
        }
      })
      .catch(() => {
        preview.style.display = "none";
        empty.style.display = "block";
      });

    // Abrir selector de archivo
    btnSeleccionar.addEventListener("click", () => inputFile.click());

    // Mostrar nombre del archivo seleccionado
    inputFile.addEventListener("change", () => {
      if (inputFile.files.length > 0) {
        fileName.textContent = inputFile.files[0].name;
        btnSubir.style.display = "inline-block";
      }
    });

    // Subir imagen
    btnSubir.addEventListener("click", () => {
      if (!inputFile.files.length) return;

      const formData = new FormData();
      formData.append("imagen_radio", inputFile.files[0]);

      btnSubir.disabled = true;
      btnSubir.textContent = "Subiendo...";
      msg.textContent = "";

      fetch(URLS.imagenSubir, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf() },
        body: formData
      })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          msg.style.color = "#00ff88";
          msg.textContent = "✅ " + data.mensaje;
          thumb.src = data.url_preview + "?t=" + Date.now();
          preview.style.display = "block";
          empty.style.display = "none";
          fileName.textContent = "";
          btnSubir.style.display = "none";
          inputFile.value = "";
        } else {
          msg.style.color = "#ff3b30";
          msg.textContent = "❌ " + data.error;
        }
      })
      .catch(() => {
        msg.style.color = "#ff3b30";
        msg.textContent = "❌ Error de red al subir la imagen";
      })
      .finally(() => {
        btnSubir.disabled = false;
        btnSubir.textContent = "⬆️ Guardar imagen";
      });
    });

    // Eliminar imagen
    btnEliminar.addEventListener("click", () => {
      if (!confirm("¿Seguro que querés eliminar la imagen de radio?")) return;

      fetch(URLS.imagenEliminar, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf() }
      })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          preview.style.display = "none";
          empty.style.display = "block";
          msg.style.color = "#00ff88";
          msg.textContent = "✅ " + data.mensaje;
        } else {
          msg.style.color = "#ff3b30";
          msg.textContent = "❌ " + data.error;
        }
      })
      .catch(() => {
        msg.style.color = "#ff3b30";
        msg.textContent = "❌ Error de red al eliminar";
      });
    });
  }

})();