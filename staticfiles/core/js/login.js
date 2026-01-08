// core/static/core/js/login.js

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".login-form");
  const usernameInput = document.getElementById("username");
  const passwordInput = document.getElementById("password");
  const passwordDots = document.querySelector(".password-dots");
  const loginButton = document.querySelector(".btn-login");

  // Validación básica
  if (form) {
    form.addEventListener("submit", (e) => {
      const username = usernameInput.value.trim();
      const password = passwordInput.value.trim();

      if (!username || !password) {
        e.preventDefault();
        alert("Por favor, completa usuario y contraseña.");
      }
    });
  }

  // Ocultar/mostrar puntos en el campo de contraseña
  if (passwordInput && passwordDots) {
    passwordInput.addEventListener("input", () => {
      passwordDots.style.opacity = passwordInput.value.length > 0 ? "0" : "1";
    });

    passwordInput.addEventListener("focus", () => {
      passwordDots.style.opacity = "0";
    });

    passwordInput.addEventListener("blur", () => {
      if (passwordInput.value.length === 0) {
        passwordDots.style.opacity = "1";
      }
    });
  }

  // Feedback visual mínimo en el botón
  if (loginButton) {
    loginButton.addEventListener("mousedown", () => {
      loginButton.style.transform = "scale(0.97)";
    });
    loginButton.addEventListener("mouseup", () => {
      loginButton.style.transform = "scale(1)";
    });
  }
});
