document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".login-form");

  if (form) {
    form.addEventListener("submit", (e) => {
      const username = document.getElementById("username").value.trim();
      const password = document.getElementById("password").value.trim();

      if (!username || !password) {
        e.preventDefault();
        // Podrías agregar una clase de error visual aquí si quisieras
        alert("Por favor, completa usuario y contraseña.");
      }
    });
  }
});