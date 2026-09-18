from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from talentia.platform.security.contrasenas import nuevo_csrf
from talentia.shared.infrastructure.base_datos import crear_motor
from talentia.shared.infrastructure.modelos_orm import (
    CandidatoModelo,
    EventoAuditoriaModelo,
    ExcolaboradorModelo,
)
from talentia.shared.infrastructure.repositorio_sqlalchemy import RepositorioSqlalchemy


def _crear_lote(cliente_api, contenido: bytes, clave: str = "fase-5-lote"):
    return cliente_api["cliente"].post(
        "/api/v1/import-batches",
        data={
            "cliente_id": cliente_api["cliente_id"],
            "tipo": "candidatos",
            "clave_idempotencia": clave,
        },
        files={"archivo": ("candidatos.csv", contenido, "text/csv")},
        headers=cliente_api["cabeceras"],
    )


def _cabeceras_otro_cliente(cliente_api, rol: str) -> dict[str, str]:
    token = cliente_api["token_para"](
        "usuario-otro-cliente",
        "otro@pruebas.test",
        [rol],
        ["cliente-no-autorizado"],
        nuevo_csrf(),
    )
    return {"Authorization": f"Bearer {token}"}


def test_lote_parcial_se_mapea_corrige_y_confirma(cliente_api) -> None:
    respuesta = _crear_lote(
        cliente_api,
        b"nombre,apellido,correo\nAna,Lote,correo-invalido\n",
    )
    assert respuesta.status_code == 201
    lote_id = respuesta.json()["id"]
    detalle = cliente_api["cliente"].get(
        f"/api/v1/import-batches/{lote_id}", headers=cliente_api["cabeceras"]
    )
    assert detalle.json()["filas"][0]["clasificacion"] == "invalida"

    mapeado = cliente_api["cliente"].patch(
        f"/api/v1/import-batches/{lote_id}/mapping",
        json={"columnas": {"nombre": "nombres", "apellido": "apellidos"}},
        headers=cliente_api["cabeceras"],
    )
    assert mapeado.status_code == 200
    assert "correo" in " ".join(mapeado.json()["filas"][0]["errores"]).casefold()

    corregido = cliente_api["cliente"].patch(
        f"/api/v1/import-batches/{lote_id}/rows/1",
        json={"datos": {"correo": "ana.lote@pruebas.test"}},
        headers=cliente_api["cabeceras"],
    )
    assert corregido.json()["filas"][0]["clasificacion"] == "nueva"
    confirmado = cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"]
    )
    assert confirmado.json()["importadas"] == 1


def test_lote_invalido_no_persiste_y_puede_cancelarse(cliente_api) -> None:
    lote = _crear_lote(cliente_api, b"nombres,apellidos\nSolo,\n", "fase-5-invalido")
    lote_id = lote.json()["id"]
    confirmacion = cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"]
    )
    assert confirmacion.status_code == 409
    cancelado = cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/cancel", headers=cliente_api["cabeceras"]
    )
    assert cancelado.json()["estado"] == "cancelado"
    repetido = cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/cancel", headers=cliente_api["cabeceras"]
    )
    assert repetido.json()["reutilizado"] is True


def test_reintentos_de_lote_no_duplican_datos_ni_eventos(cliente_api) -> None:
    contenido = b"nombres,apellidos,documento\nInes,Unica,DNI-100\n"
    primero = _crear_lote(cliente_api, contenido, "fase-5-idempotente")
    segundo = _crear_lote(cliente_api, contenido, "fase-5-idempotente")
    assert segundo.json()["id"] == primero.json()["id"]
    lote_id = primero.json()["id"]
    cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"]
    )
    cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"]
    )
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        candidatos = sesion.scalar(select(func.count()).select_from(CandidatoModelo))
        eventos = sesion.scalar(
            select(func.count())
            .select_from(EventoAuditoriaModelo)
            .where(
                EventoAuditoriaModelo.recurso_id == lote_id,
                EventoAuditoriaModelo.accion.in_(["lote.preparado", "lote.confirmado"]),
            )
        )
    assert candidatos == 1
    assert eventos == 2


def test_duplicado_dentro_del_archivo_se_omite_sin_duplicar(cliente_api) -> None:
    lote = _crear_lote(
        cliente_api,
        (b"nombres,apellidos,documento\nMario,Duplicado,DNI-200\nMario,Duplicado,DNI-200\n"),
        "fase-5-duplicado-interno",
    )
    lote_id = lote.json()["id"]
    detalle = (
        cliente_api["cliente"]
        .get(f"/api/v1/import-batches/{lote_id}", headers=cliente_api["cabeceras"])
        .json()
    )
    assert [fila["clasificacion"] for fila in detalle["filas"]] == ["nueva", "exacta"]
    resultado = (
        cliente_api["cliente"]
        .post(f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"])
        .json()
    )
    assert (resultado["importadas"], resultado["omitidas"]) == (1, 1)


def test_confirmacion_fallida_revierte_toda_la_transaccion(cliente_api, monkeypatch) -> None:
    lote = _crear_lote(
        cliente_api,
        b"nombres,apellidos,documento\nRosa,Rollback,DNI-ROLLBACK\n",
        "fase-5-rollback",
    )
    lote_id = lote.json()["id"]

    def fallar_importacion(self, lote_modelo, filas):
        self.sesion.add(
            CandidatoModelo(
                id="candidato-que-debe-revertirse",
                cliente_id=lote_modelo.cliente_id,
                nombres="Rosa",
                apellidos="Rollback",
                estado="nuevo",
                etiquetas=[],
                version=1,
            )
        )
        self.sesion.flush()
        raise RuntimeError("fallo controlado")

    monkeypatch.setattr(RepositorioSqlalchemy, "_importar_candidatos", fallar_importacion)
    with pytest.raises(RuntimeError, match="fallo controlado"):
        cliente_api["cliente"].post(
            f"/api/v1/import-batches/{lote_id}/confirm", headers=cliente_api["cabeceras"]
        )
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        assert sesion.get(CandidatoModelo, "candidato-que-debe-revertirse") is None


def test_lotes_impiden_acceso_cruzado(cliente_api) -> None:
    lote = _crear_lote(cliente_api, b"nombres,apellidos\nLia,Segura\n", "fase-5-idor")
    cabeceras = _cabeceras_otro_cliente(cliente_api, "importador")
    respuesta = cliente_api["cliente"].get(
        f"/api/v1/import-batches/{lote.json()['id']}", headers=cabeceras
    )
    assert respuesta.status_code == 403


def test_excolaborador_se_minimiza_y_solo_genera_revision(cliente_api) -> None:
    documento = "DNI-87654321"
    lote = cliente_api["cliente"].post(
        "/api/v1/former-employees/imports",
        data={
            "cliente_id": cliente_api["cliente_id"],
            "clave_idempotencia": "fase-5-ex-tcs",
        },
        files={
            "archivo": (
                "excolaboradores.csv",
                f"documento,elegible_reingreso\n{documento},si\n".encode(),
                "text/csv",
            )
        },
        headers=cliente_api["cabeceras"],
    )
    cliente_api["cliente"].post(
        f"/api/v1/import-batches/{lote.json()['id']}/confirm",
        headers=cliente_api["cabeceras"],
    )
    comprobacion = cliente_api["cliente"].post(
        "/api/v1/former-employees/checks",
        json={"cliente_id": cliente_api["cliente_id"], "documento": documento},
        headers=cliente_api["cabeceras"],
    )
    assert comprobacion.json() == {
        "coincidencia": True,
        "requiere_revision": False,
        "bloqueada_politica": True,
        "resultado": "bloqueada_politica",
    }
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        registro = sesion.scalar(select(ExcolaboradorModelo))
        assert registro is not None
        assert registro.documento_hash == hashlib.sha256(b"DNI87654321").hexdigest()
        assert documento not in str(registro.__dict__)
    otro = cliente_api["cliente"].post(
        "/api/v1/former-employees/checks",
        json={"cliente_id": cliente_api["cliente_id"], "documento": documento},
        headers=_cabeceras_otro_cliente(cliente_api, "importador"),
    )
    assert otro.status_code == 403


def test_reporte_es_idempotente_integro_auditado_y_aislado(cliente_api) -> None:
    entrada = {"cliente_id": cliente_api["cliente_id"], "filtros": {"estado": "descartado"}}
    primero = cliente_api["cliente"].post(
        "/api/v1/exclusion-reports", json=entrada, headers=cliente_api["cabeceras"]
    )
    segundo = cliente_api["cliente"].post(
        "/api/v1/exclusion-reports", json=entrada, headers=cliente_api["cabeceras"]
    )
    assert segundo.json()["id"] == primero.json()["id"]
    assert segundo.json()["reutilizado"] is True
    reporte_id = primero.json()["id"]
    consulta = cliente_api["cliente"].get(
        f"/api/v1/exclusion-reports/{reporte_id}", headers=cliente_api["cabeceras"]
    )
    assert consulta.status_code == 200
    assert consulta.json()["entradas"] == []
    actualizado = cliente_api["cliente"].patch(
        f"/api/v1/exclusion-reports/{reporte_id}",
        json={"filtros": {}},
        headers=cliente_api["cabeceras"],
    )
    assert actualizado.status_code == 200
    descarga = cliente_api["cliente"].get(
        f"/api/v1/exclusion-reports/{reporte_id}/download",
        headers=cliente_api["cabeceras"],
    )
    assert descarga.status_code == 200
    assert descarga.content.decode("utf-8-sig") == "documento,motivo\r\n"
    denegada = cliente_api["cliente"].get(
        f"/api/v1/exclusion-reports/{reporte_id}/download",
        headers=_cabeceras_otro_cliente(cliente_api, "auditor"),
    )
    assert denegada.status_code == 403
    motor = crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}")
    with Session(motor) as sesion:
        acciones = set(
            sesion.scalars(
                select(EventoAuditoriaModelo.accion).where(
                    EventoAuditoriaModelo.recurso_id == reporte_id
                )
            )
        )
    assert {
        "exclusion.exportada",
        "exclusion.actualizada",
        "exclusion.consultada",
        "exclusion.descargada",
    } <= acciones


def test_recorrido_web_de_lote_y_exclusion(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    token = cliente_api["cabeceras"]["Authorization"].removeprefix("Bearer ")
    cliente.cookies.set("talentia_session", token)
    csrf = cliente.app.state.firmador.leer(token)["csrf"]
    formulario = cliente.get("/lotes/nuevo")
    assert formulario.status_code == 200
    assert "Cargar y revisar" in formulario.text
    carga = cliente.post(
        "/lotes/nuevo",
        data={
            "csrf": csrf,
            "cliente_id": cliente_api["cliente_id"],
            "tipo": "candidatos",
            "clave_idempotencia": "fase-5-web",
        },
        files={
            "archivo": (
                "candidatos.csv",
                b"nombres,apellidos,documento\nElena,Web,DNI-WEB-5\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert carga.status_code == 303
    detalle = cliente.get(carga.headers["location"])
    assert "Los datos no se incorporan hasta confirmar" in detalle.text
    lote_id = carga.headers["location"].rsplit("/", 1)[-1]
    confirmacion = cliente.post(
        f"/lotes/{lote_id}/confirmar", data={"csrf": csrf}, follow_redirects=True
    )
    assert confirmacion.status_code == 200
    assert "confirmado" in confirmacion.text
    reporte = cliente.post(
        "/exclusiones/nueva",
        data={"csrf": csrf, "cliente_id": cliente_api["cliente_id"], "estado": "nuevo"},
        follow_redirects=True,
    )
    assert reporte.status_code == 200
    assert "Integridad SHA-256" in reporte.text
