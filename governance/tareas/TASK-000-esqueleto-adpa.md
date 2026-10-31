```toml
id = "TASK-000"
titulo = "Esqueleto ADPA, compose, arnés, CI y backups probados"
fase = 0
estado = "boceto"
sala = ["app_core", "infraestructura", "todas (compuertas vacías)"]
rastro = ["¤pasillo-central", "¤infra-hibrida", "¤arquitectura-salas", "¤bbap-glamping"]
rol = "¤¤solutions-architect"
depende_de = []
bloqueada_por = []
propiedad = ["app_core/**", "features/*/<sala>_service.py", "features/*/config_<sala>.yaml", "compose.yaml", "compose.production.yaml", ".env.example", "ejecutar_arnes_glamping.bat", "ejecutar_arnes_glamping.sh", "pyproject.toml", "tests/test_estructura_adpa.py", "tests/test_canal_oficial.py", "tests/test_sin_clientes_ota.py", ".github/workflows/ci.yml"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0): tests de estructura + canal oficial + compose config + escáner de secretos; restauración de backup documentada"
```

# TASK-000 — Esqueleto ADPA, compose, arnés, CI y backups probados
`¤pasillo-central` `¤infra-hibrida`

## Objetivo
Materializar la estructura de [`ARQUITECTURA.md` §3.1](../../docs/ARQUITECTURA.md) con compuertas vacías pero importables, el pasillo central, los dos archivos compose, el arnés físico y la CI, de modo que las fases siguientes solo llenen salas.

## Entregables
1. `app_core/main.py` (salud `GET /health`), `app_core/contenedor.py` (construye compuertas), `app_core/config_app.yaml`.
2. `features/<sala>/<sala>_service.py` con la interfaz declarada y `NotImplementedError`, más `config_<sala>.yaml`, para: `canal_whatsapp`, `seguridad`, `agente`, `conocimiento`, `pms_conector`, `crm_conector`, `arm_jarvis`, `comisiones`, `observabilidad`; `features/herramientas_glamping/server.py`.
3. `compose.yaml` + `compose.production.yaml` según [`ARQUITECTURA.md` §6](../../docs/ARQUITECTURA.md); `.env.example` sin valores.
4. `ejecutar_arnes_glamping.bat` y `.sh`: `adpa_linter` → `huellas_linter` → UTF-8 → escáner de secretos → `pytest` → `scripts/run_evals.py` (vacío por ahora) → escribe `governance/artefactos/data/.test_verdict.json` con Exit Code.
5. `tests/test_estructura_adpa.py`, `tests/test_canal_oficial.py`, `tests/test_sin_clientes_ota.py`.
6. CI que ejecuta el arnés y `docker compose -f compose.yaml -f compose.production.yaml config`.
7. Proveedor de PostgreSQL gestionado elegido (Neon o Render; menor, revisable por ADR-0012) y PITR documentado en `INVARIANTS.md` (`INV_PITR_MINIMO`).
8. Primer backup externo del repositorio y `governance/` restaurado y documentado (RNF-15).

## Criterios de fase completada
- Arnés en Exit Code 0 con los tres tests de raíz.
- `docker compose ... config` válido.
- Certificado `.test_verdict.json` presente.

## Notas ZERAG
Boceto libre; al sellar, cero `¦` y `adpa_linter` limpio. Esta tarea es la única que toca `app_core/` y la infraestructura: las siguientes solo añaden a sus salas.

## Avance (2026-10-30)
La fase sigue en `boceto`: faltan los dos pendientes del propietario de abajo. Una CI en rojo mostró que el primer arnés local omitía `docker compose config` y aun así decía aprobado; ahora el certificado declara `APROBADO_CON_OMISIONES` en ese caso.

- Arnés `ejecutar_arnes_glamping` en Exit Code 0: UTF-8 sin BOM, escáner de secretos, 46 pruebas, evaluaciones (4 suites omitidas por no existir aún sus archivos de casos), YAML de compose válidos. Certificado en `governance/artefactos/data/.test_verdict.json`.
- Once salas con compuerta, `tipos.py`, `config_<sala>.yaml` e `__init__.py`; `app_core/` con compuerta `app_core_service.py`, `contenedor.py` (privado), `main.py` y `config_app.yaml`; `features/herramientas_glamping/server.py` como ejecutable MCP.
- `compose.yaml`, `compose.production.yaml`, `Dockerfile`, `infra/Caddyfile`, `.env.example`, `.gitignore`, `pyproject.toml`, `.github/workflows/ci.yml`.
- Ajuste respecto al diseño: el pasillo central expone `app_core_service.py` porque el linter ADPA solo reconoce compuertas con sufijo `_service`; `contenedor.py` pasa a ser privado. El orden de construcción cambió para que `canal_whatsapp` exista antes que `agente` y `arm_jarvis` (que lo usan para enviar); los receptores se registran al final.
- `docker compose config` se omite en local cuando docker no está en el PATH, queda declarado en el certificado y lo ejecuta la CI en cada push, junto con el DDL en PostgreSQL real.

## Pendientes del propietario (fuera del alcance de la IA)
7. Elegir el proveedor de PostgreSQL gestionado (Neon o Render; sujeto a ADR-0012) y documentar su PITR en `INVARIANTS.md` (`INV_PITR_MINIMO`).
8. Ejecutar y documentar la primera restauración de backup externo del repositorio y de `governance/` (RNF-15).
