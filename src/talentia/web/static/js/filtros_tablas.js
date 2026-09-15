"use strict";

document.addEventListener("input", (evento) => {
  const campo = evento.target;
  if (!(campo instanceof HTMLInputElement)) return;
  const tablaId = campo.dataset.filterTable;
  if (!tablaId) return;
  const tabla = document.getElementById(tablaId);
  if (!tabla) return;
  const consulta = campo.value.trim().toLocaleLowerCase("es");
  tabla.querySelectorAll("tbody tr").forEach((fila) => {
    const contenido = (fila.textContent || "").toLocaleLowerCase("es");
    fila.hidden = !contenido.includes(consulta);
  });
});
