// ver_usuarios.js
document.addEventListener("DOMContentLoaded", () => {
  const deleteButtons = document.querySelectorAll(".btn--delete");

  deleteButtons.forEach(btn => {
    btn.addEventListener("click", (e) => {
      const confirmDelete = confirm("¿Seguro que deseas eliminar este usuario?");
      if (!confirmDelete) {
        e.preventDefault();
      }
    });
  });
});
  