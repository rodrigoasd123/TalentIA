"""Registro de prompts versionados.

Los prompts no viven dentro del código. Viven en ficheros YAML con versión,
modelo objetivo, temperatura y esquema de salida declarados. Tres motivos:

1. **Reproducibilidad**: una evaluación guarda con qué versión de prompt se
   hizo. Sin eso, "¿por qué se rechazó a esta persona?" no tiene respuesta
   completa seis meses después.
2. **Control de cambios**: un prompt es tan crítico como el código. Cambiarlo
   debe pasar por la suite de evaluación antes de llegar a producción.
3. **Inmutabilidad**: una versión publicada no se edita. Se crea otra. Editar
   una versión existente rompería la trazabilidad de todo lo evaluado con ella.

El registro carga los ficheros una vez y los cachea. En caliente no se puede
modificar un prompt: no existe método para ello, y esa ausencia es la garantía
de que ningún camino de la aplicación —ni una inyección— puede alterarlos.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.ai.schemas import OUTPUT_SCHEMAS
from app.core.config import PROMPTS_DIR
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class PromptVersion:
    """Una versión concreta de un prompt, inmutable por construcción."""

    name: str
    version: str
    description: str
    system_instruction: str
    user_template: str
    output_schema: str
    temperature: float
    max_output_tokens: int
    target_models: tuple[str, ...]
    author: str
    created_at: str
    checksum: str

    @property
    def full_id(self) -> str:
        return f"{self.name}@{self.version}"

    def render_user(self, **variables: Any) -> str:
        """Rellena la plantilla del mensaje de usuario.

        Se usa ``str.format`` sobre marcadores explícitos en lugar de un motor
        de plantillas con lógica: un prompt no debe poder ejecutar nada.
        """
        try:
            return self.user_template.format(**variables)
        except KeyError as exc:
            raise ValueError(
                f"Falta la variable {exc} al renderizar el prompt {self.full_id}"
            ) from exc

    def schema_model(self) -> type:
        model = OUTPUT_SCHEMAS.get(self.output_schema)
        if model is None:
            raise ValueError(
                f"El prompt {self.full_id} declara un esquema desconocido: {self.output_schema}"
            )
        return model

    def metadata(self) -> dict[str, Any]:
        """Datos que se guardan junto a cada ejecución para poder reproducirla."""
        return {
            "prompt_name": self.name,
            "prompt_version": self.version,
            "prompt_checksum": self.checksum,
            "output_schema": self.output_schema,
            "temperature": self.temperature,
        }


class PromptRegistry:
    """Carga y sirve los prompts versionados desde disco."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or PROMPTS_DIR
        self._cache: dict[str, PromptVersion] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        if not self.directory.exists():
            raise FileNotFoundError(
                f"No existe el directorio de prompts: {self.directory}"
            )
        for path in sorted(self.directory.glob("*.yaml")):
            prompt = self._parse(path)
            self._cache[prompt.full_id] = prompt
            # También se indexa por nombre, apuntando a la versión más alta.
            current = self._cache.get(prompt.name)
            if current is None or prompt.version > current.version:
                self._cache[prompt.name] = prompt
        self._loaded = True
        logger.info(
            "Prompts cargados",
            count=len({p.full_id for p in self._cache.values()}),
            directory=str(self.directory),
        )

    @staticmethod
    def _parse(path: Path) -> PromptVersion:
        raw = path.read_text(encoding="utf-8")
        data: dict[str, Any] = yaml.safe_load(raw) or {}
        missing = {"name", "version", "system_instruction", "user_template", "output_schema"} - set(data)
        if missing:
            raise ValueError(f"El prompt {path.name} no declara: {', '.join(sorted(missing))}")
        return PromptVersion(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data.get("description", "")),
            system_instruction=str(data["system_instruction"]).strip(),
            user_template=str(data["user_template"]),
            output_schema=str(data["output_schema"]),
            temperature=float(data.get("temperature", 0.1)),
            max_output_tokens=int(data.get("max_output_tokens", 4096)),
            target_models=tuple(data.get("target_models", ())),
            author=str(data.get("author", "")),
            created_at=str(data.get("created_at", "")),
            # El checksum es del contenido literal del fichero: si alguien edita
            # una versión publicada, se detecta al comparar con lo registrado.
            checksum=hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
        )

    def get(self, name: str, version: str | None = None) -> PromptVersion:
        """Obtiene un prompt. Sin versión, devuelve la más reciente."""
        self._load()
        key = f"{name}@{version}" if version else name
        prompt = self._cache.get(key)
        if prompt is None:
            available = sorted({p.full_id for p in self._cache.values()})
            raise KeyError(f"Prompt no encontrado: {key}. Disponibles: {available}")
        return prompt

    def list_all(self) -> list[PromptVersion]:
        self._load()
        return sorted({p.full_id: p for p in self._cache.values()}.values(), key=lambda p: p.full_id)

    def versions_of(self, name: str) -> list[PromptVersion]:
        self._load()
        return sorted(
            (p for p in self._cache.values() if p.name == name and "@" in p.full_id),
            key=lambda p: p.version,
        )


@lru_cache(maxsize=1)
def get_prompt_registry() -> PromptRegistry:
    return PromptRegistry()


__all__ = ["PromptRegistry", "PromptVersion", "get_prompt_registry"]
