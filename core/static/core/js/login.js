// ===== Login Page Script =====
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".login-form");

  form.addEventListener("submit", (e) => {
    // Validación básica antes de enviar
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value.trim();

    if (!username || !password) {
      e.preventDefault();
      alert("Por favor, completa todos los campos.");
      return;
    }

    // Podés agregar lógica extra aquí (ejemplo: mostrar spinner)
    console.log("Intentando login con:", username);
  });
});
