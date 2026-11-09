document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("menuToggle");
  if (sidebar && toggle) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
    document.addEventListener("click", (event) => {
      if (
        sidebar.classList.contains("open") &&
        !sidebar.contains(event.target) &&
        !toggle.contains(event.target)
      ) {
        sidebar.classList.remove("open");
      }
    });
  }

  document.querySelectorAll("[data-confirm]").forEach((element) => {
    element.addEventListener("click", (event) => {
      if (!window.confirm(element.dataset.confirm)) {
        event.preventDefault();
      }
    });
  });

  // Плавное скрытие уведомлений.
  document.querySelectorAll(".alert").forEach((alert) => {
    window.setTimeout(() => {
      alert.style.transition = "opacity .4s ease, transform .4s ease";
      alert.style.opacity = "0";
      alert.style.transform = "translateY(-6px)";
      window.setTimeout(() => alert.remove(), 450);
    }, 6500);
  });
});
