// crear_usuario.js
document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector(".form");
  const cancel = document.getElementById("btnCancel");

  // Cancel → go back to previous page
  cancel.addEventListener("click", () => {
    if (document.referrer) {
      window.location.href = document.referrer;
    } else {
      window.history.back();
    }
  });

  // Basic client-side validation to improve UX without fighting Django's server validation
  form.addEventListener("submit", (e) => {
    const requiredInputs = form.querySelectorAll("input[required]");
    let firstInvalid = null;

    requiredInputs.forEach((input) => {
      const valid = input.value.trim().length > 0;
      input.classList.toggle("invalid", !valid);
      if (!valid && !firstInvalid) firstInvalid = input;
    });

    if (firstInvalid) {
      e.preventDefault();
      firstInvalid.focus();
    }
  });
});
