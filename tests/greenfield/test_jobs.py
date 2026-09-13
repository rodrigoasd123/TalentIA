from talentia.platform.jobs.worker import procesar_siguiente
from talentia.shared.infrastructure.base_datos import FabricaSesiones, crear_motor


def test_trabajo_sobrevive_y_se_completa_fuera_de_la_peticion(cliente_api) -> None:
    cliente = cliente_api["cliente"]
    cabeceras = cliente_api["cabeceras"]
    solicitud = cliente.post(
        "/api/v1/applications/post-1/evaluation-jobs",
        headers=cabeceras,
        json={
            "cliente_id": cliente_api["cliente_id"],
            "documento_id": "doc-1",
            "version_perfil_id": "perfil-1",
            "clave_idempotencia": "trabajo-prueba-1",
        },
    )
    assert solicitud.status_code == 202
    trabajo_id = solicitud.json()["id"]
    fabrica = FabricaSesiones(crear_motor(f"sqlite:///{cliente_api['base'].as_posix()}"))
    assert procesar_siguiente(fabrica) == trabajo_id
    estado = cliente.get(f"/api/v1/jobs/{trabajo_id}", headers=cabeceras).json()
    assert estado["estado"] == "completado"
    assert estado["resultado"]["es_simulacion"] is False
