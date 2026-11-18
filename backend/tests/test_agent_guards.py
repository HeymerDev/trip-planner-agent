"""Barandillas deterministas del Orchestrator para acciones con dinero (app/OrchestratorAgent/ui.py)."""

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "OrchestratorAgent"))


@pytest.fixture
def ui():
    module = importlib.import_module("ui")
    module = importlib.reload(module)  # estado limpio por prueba
    return module


def turn(ui, session, prompt):
    return ui.begin("Bearer a.b.c", session, prompt)


def test_afirmaciones_y_negaciones(ui):
    for text in ["Sí, confirmo la compra", "si", "dale", "Confirmo", "ok, adelante", "sí, págalo"]:
        assert ui.is_affirmative(text), text
    for text in ["no", "No, mejor no", "cancela eso", "todavía no", "", "quiero ver más hoteles", "sin escalas por favor"]:
        assert not ui.is_affirmative(text), text


def test_la_compra_no_se_cobra_en_el_mismo_turno_que_se_pide(ui):
    turn(ui, "s1", "Reserva el hotel Sol de Alba")
    first = ui.purchase_gate("trip123456", 567145)
    assert first and "CONFIRMATION_REQUIRED" in first and '"charged": false' in first
    # El modelo insiste en el mismo turno: sigue bloqueado aunque diga "reserva"
    assert ui.purchase_gate("trip123456", 567145) is not None


def test_cobra_solo_tras_confirmacion_en_un_turno_posterior(ui):
    turn(ui, "s2", "Quiero reservar el hotel")
    assert ui.purchase_gate("trip123456", 567145) is not None
    turn(ui, "s2", "Sí, confirmo")
    assert ui.purchase_gate("trip123456", 567145) is None  # ahora sí
    # y se consume: una segunda compra vuelve a exigir confirmación
    turn(ui, "s2", "Sí, confirmo")
    assert ui.purchase_gate("trip123456", 567145) is not None


def test_no_cobra_si_el_usuario_no_confirma_o_cambia_el_monto(ui):
    turn(ui, "s3", "Reserva el hotel")
    ui.purchase_gate("trip123456", 567145)
    turn(ui, "s3", "mejor no, muéstrame otras opciones")
    assert ui.purchase_gate("trip123456", 567145) is not None
    turn(ui, "s3", "Reserva el hotel")
    ui.purchase_gate("trip123456", 567145)
    turn(ui, "s3", "sí")
    assert ui.purchase_gate("trip123456", 999999) is not None  # otro monto: pide confirmar de nuevo


def test_las_sesiones_no_se_mezclan(ui):
    turn(ui, "a", "Reserva")
    ui.purchase_gate("trip123456", 100000)
    turn(ui, "b", "Sí, confirmo")
    assert ui.purchase_gate("trip123456", 100000) is not None  # la confirmación de B no sirve para A


def test_recarga_solo_si_el_usuario_la_pide(ui):
    turn(ui, "r1", "Recarga 3.000.000 COP en mi monedero")
    assert ui.topup_allowed()
    turn(ui, "r1", "Quiero reservar un hotel")
    assert not ui.topup_allowed()


def test_extraccion_de_bloques_ui_y_sub(ui):
    clean, events = ui.extract_ui('Texto <ui>{"component":"flights","data":{"a":1}}</ui> y <ui>{malo}</ui> fin')
    assert clean == "Texto  y  fin" and events == [{"component": "flights", "data": {"a": 1}}]
    assert ui._sub_from_jwt("x.e30.y") == ""


def test_solo_se_aceptan_enlaces_entregados_por_especialistas(ui):
    turn(ui, "l1", "busca hoteles")
    ui.remember_links('[Reservar](https://staylist.world/api/hotels/x?k=1&via=agent). <ui>{"u":"https://t.com/a"}</ui>')
    assert ui.known_link("https://staylist.world/api/hotels/x?k=1&via=agent")
    assert ui.known_link("https://t.com/a")
    assert not ui.known_link("https://www.booking.com")  # inventado por el modelo
    turn(ui, "l2", "otra sesion")
    assert not ui.known_link("https://t.com/a")  # los enlaces no cruzan sesiones
