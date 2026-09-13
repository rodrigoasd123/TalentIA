"""Errores tipados que API y web traducen sin filtrar detalles internos."""


class TalentIAError(RuntimeError):
    codigo = "error_talentia"
    estado_http = 400


class NoAutorizadoError(TalentIAError):
    codigo = "no_autorizado"
    estado_http = 401


class ProhibidoError(TalentIAError):
    codigo = "prohibido"
    estado_http = 403


class NoEncontradoError(TalentIAError):
    codigo = "no_encontrado"
    estado_http = 404


class ConflictoError(TalentIAError):
    codigo = "conflicto"
    estado_http = 409


class DecisionNegocioPendienteError(TalentIAError):
    codigo = "decision_negocio_pendiente"
    estado_http = 422


class EntradaInvalidaError(TalentIAError):
    codigo = "entrada_invalida"
    estado_http = 422
