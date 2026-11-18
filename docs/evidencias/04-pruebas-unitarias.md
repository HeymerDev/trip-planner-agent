# Evidencia 04 — Pruebas unitarias

Fecha: 2026-11-16 21:47 UTC

## Backend (pytest + moto, DynamoDB y memoria simuladas)

```
tests/test_agent_guards.py::test_afirmaciones_y_negaciones PASSED
tests/test_agent_guards.py::test_la_compra_no_se_cobra_en_el_mismo_turno_que_se_pide PASSED
tests/test_agent_guards.py::test_cobra_solo_tras_confirmacion_en_un_turno_posterior PASSED
tests/test_agent_guards.py::test_no_cobra_si_el_usuario_no_confirma_o_cambia_el_monto PASSED
tests/test_agent_guards.py::test_las_sesiones_no_se_mezclan PASSED
tests/test_agent_guards.py::test_recarga_solo_si_el_usuario_la_pide PASSED
tests/test_agent_guards.py::test_extraccion_de_bloques_ui_y_sub PASSED
tests/test_agent_guards.py::test_solo_se_aceptan_enlaces_entregados_por_especialistas PASSED
tests/test_backend.py::test_sin_token_devuelve_401 PASSED
tests/test_backend.py::test_ruta_desconocida_404 PASSED
tests/test_backend.py::test_usuario_no_ve_ni_modifica_viajes_ajenos PASSED
tests/test_backend.py::test_el_cuerpo_no_puede_cambiar_el_dueno PASSED
tests/test_backend.py::test_reserva_ajena_404_y_no_se_asocia_a_viaje_ajeno PASSED
tests/test_backend.py::test_viaje_invalido_lista_todos_los_campos PASSED
tests/test_backend.py::test_fechas_invertidas_y_viaje_demasiado_largo PASSED
tests/test_backend.py::test_json_invalido_y_cuerpo_no_objeto PASSED
tests/test_backend.py::test_travelers_booleano_o_decimal_se_rechaza PASSED
tests/test_backend.py::test_id_con_formato_invalido_404 PASSED
tests/test_backend.py::test_reserva_valida_tipo_y_url PASSED
tests/test_backend.py::test_crud_de_viaje_y_nombre_por_defecto PASSED
tests/test_backend.py::test_itinerario_crear_ordenar_y_conflicto PASSED
tests/test_backend.py::test_itinerario_fuera_de_fechas_o_invalido PASSED
tests/test_backend.py::test_itinerario_de_viaje_ajeno_404 PASSED
tests/test_backend.py::test_reserva_simulada_estados_y_reasociacion PASSED
tests/test_backend.py::test_crear_reserva_no_permite_estado_confirmada PASSED
tests/test_backend.py::test_recarga_valida_rango_y_tope PASSED
tests/test_backend.py::test_compra_descuenta_crea_reserva_y_movimiento PASSED
tests/test_backend.py::test_saldo_insuficiente_no_cambia_nada PASSED
tests/test_backend.py::test_compra_sin_monedero_creado_es_saldo_insuficiente PASSED
tests/test_backend.py::test_idempotencia_no_cobra_dos_veces PASSED
tests/test_backend.py::test_misma_clave_de_idempotencia_en_otro_usuario_no_colisiona PASSED
tests/test_backend.py::test_cancelar_reserva_pagada_reembolsa_una_sola_vez PASSED
tests/test_backend.py::test_no_se_puede_cambiar_el_precio_de_una_reserva_pagada PASSED
tests/test_backend.py::test_compra_con_precio_cero_o_viaje_inexistente PASSED
tests/test_backend.py::test_perfil_preferencias_y_dashboard PASSED
tests/test_backend.py::test_eliminar_viaje_conserva_reservas_sin_viaje PASSED
tests/test_conversations.py::test_lista_las_conversaciones_del_usuario_con_titulo PASSED
tests/test_conversations.py::test_reconstruye_mensajes_con_herramientas_tarjetas_y_texto PASSED
tests/test_conversations.py::test_un_usuario_no_ve_las_conversaciones_de_otro PASSED
tests/test_conversations.py::test_id_de_sesion_invalido PASSED
tests/test_conversations.py::test_eliminar_borra_los_eventos_del_agente_y_de_las_tarjetas PASSED
tests/test_conversations.py::test_sin_memoria_configurada_responde_503 PASSED
tests/test_conversations.py::test_usuario_sin_conversaciones_devuelve_lista_vacia PASSED
tests/test_utils.py::test_fx_convierte_y_valida PASSED
tests/test_utils.py::test_bogota_cartagena_recomienda_avion PASSED
tests/test_utils.py::test_ciudades_cercanas_recomienda_bus PASSED
tests/test_utils.py::test_ciudad_inexistente_y_parametros_invalidos PASSED
tests/test_utils.py::test_haversine PASSED
============================= 48 passed in 33.52s =============================
```

## Frontend (vitest)

```
 ✓ src/lib/sse.test.js > parser SSE > une eventos partidos en varios chunks
 ✓ src/lib/sse.test.js > parser SSE > tolera CRLF, lineas basura y JSON doblemente serializado
 ✓ src/lib/sse.test.js > parser SSE > flush entrega el ultimo bloque sin linea en blanco
 ✓ src/lib/sse.test.js > parser SSE > reconoce el inicio de una herramienta
 ✓ src/lib/sse.test.js > helpers > safeUrl solo permite http(s)
 ✓ src/lib/sse.test.js > helpers > durationMinutes
 Test Files  1 passed (1)
      Tests  6 passed (6)
```
