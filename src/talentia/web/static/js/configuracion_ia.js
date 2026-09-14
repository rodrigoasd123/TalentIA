(() => {
  "use strict";

  const selector = document.querySelector("#modelo-ia");
  const proveedores = document.querySelectorAll('input[name="proveedor"]');
  const temperatura = document.querySelector("#temperatura-ia");
  const salidaTemperatura = document.querySelector("#valor-temperatura");

  const sincronizarModelos = () => {
    if (!selector) return;
    const activo = document.querySelector('input[name="proveedor"]:checked')?.value;
    let primera = null;
    selector.querySelectorAll("optgroup").forEach((grupo) => {
      const visible = grupo.dataset.provider === activo;
      grupo.hidden = !visible;
      grupo.querySelectorAll("option").forEach((opcion) => {
        opcion.disabled = !visible;
        if (visible && primera === null) primera = opcion;
      });
    });
    if (selector.selectedOptions[0]?.disabled && primera) primera.selected = true;
  };

  proveedores.forEach((radio) => radio.addEventListener("change", sincronizarModelos));
  sincronizarModelos();

  temperatura?.addEventListener("input", () => {
    if (salidaTemperatura) salidaTemperatura.value = temperatura.value;
  });

  document.querySelectorAll("[data-toggle-secret]").forEach((boton) => {
    boton.addEventListener("click", () => {
      const campo = document.getElementById(boton.dataset.toggleSecret);
      if (!campo) return;
      const mostrar = campo.type === "password";
      campo.type = mostrar ? "text" : "password";
      boton.textContent = mostrar ? "Ocultar" : "Ver";
      boton.setAttribute("aria-label", mostrar ? "Ocultar API Key" : "Mostrar API Key");
      boton.setAttribute("aria-pressed", String(mostrar));
    });
  });
})();
