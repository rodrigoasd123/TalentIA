"""Enrutador de modelos para asignar tareas específicas a modelos específicos."""

from app.core.config import get_settings

AI_MODEL_ROUTING = {
    "cv_extraction": "gpt-5.6-luna",
    "email_generation": "gpt-5.6-luna",
    "candidate_summary": "gpt-5.6-luna",
    "candidate_ranking": "gpt-5.6-terra",
    "advanced_evaluation": "gpt-5.6-terra",
}


def get_model_for_task(task_name: str) -> str:
    """Obtiene el modelo configurado para una tarea o el predeterminado."""
    if task_name in AI_MODEL_ROUTING:
        return AI_MODEL_ROUTING[task_name]
    
    settings = get_settings()
    return settings.openai_model
