# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Implementación modular para Chatwoot / Attio (RF-CRM-02)."""
from __future__ import annotations

from typing import Any, Mapping

from features.crm_conector.ghl_internal import GHLConnector
from features.crm_conector.http_internal import AdaptadorHttpCRM

__all__ = ["ChatwootAttioConnector"]


# ¤crm-conector
class ChatwootAttioConnector(GHLConnector):
    """Conector combinado Chatwoot (inbox) + Attio (sistema de registro)."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        adaptador: AdaptadorHttpCRM | None = None,
    ) -> None:
        super().__init__(config, adaptador)
