"""Interrupt raised when a connector tool call fails due to expired/invalid auth.

Mirrors ai/tools/tools.py::HumanInterruptException — both are caught by the
multi-orchestration scheduler to pause a run and persist resumable state to
the run document. This one carries connector identity instead of a question,
so the frontend can render a reconnect action instead of an answer box.
"""


class ConnectorReauthException(Exception):
    def __init__(self, connector_id: str, provider_id: str, display_name: str, fn_name: str):
        super().__init__(
            f"Connector '{display_name}' needs to be reconnected (tool={fn_name})."
        )
        self.connector_id = connector_id
        self.provider_id = provider_id
        self.display_name = display_name
        self.fn_name = fn_name

    def to_dict(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "fn_name": self.fn_name,
        }
