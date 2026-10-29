"""Environment loading and the exact model IDs SiteWork calls."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class MissingCredential(RuntimeError):
    """A required secret is not set in the environment or `.env`."""

    def __init__(self, env_var: str):
        super().__init__(f"{env_var} is not set (see .env.example and TODO_HUMAN.md)")
        self.env_var = env_var


class Settings(BaseSettings):
    """Every runtime knob, read from the environment or `.env`."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_ignore_empty=True, extra="ignore"
    )

    # Nebius Token Factory (OpenAI-compatible).
    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"

    # Exact IDs from Token Factory `GET /models`. `make check` lists the
    # candidates; record the chosen IDs here. Empty means "not yet verified".
    nebius_vlm_model: str = ""
    nebius_agent_model: str = ""
    nebius_audio_model: str = ""

    # Tavily.
    tavily_api_key: SecretStr | None = None

    # Decionis: base API plus the hosted AgentSafe gateway for gate calls.
    decionis_api_key: SecretStr | None = None
    agentsafe_tenant_key: SecretStr | None = None
    decionis_org_id: str = ""
    decionis_api_base: str = "https://api.decionis.com"
    decionis_gateway_url: str = "https://sitework.decionisedge.com"
    # A different tenant needs its own ingress key; never switch automatically.
    decionis_gateway_fallback: str = ""
    decionis_mode: Literal["live", "mock"] = "live"

    # Optional Cosmos Reason 2 served by vLLM on the Nebius AI Cloud GPU VM.
    cosmos_reason_url: str = ""

    request_timeout: float = 20.0

    def secret(self, field: str) -> str:
        """Return a secret's value or raise MissingCredential naming its env var."""
        value = getattr(self, field)
        if value is None or not value.get_secret_value():
            raise MissingCredential(field.upper())
        return value.get_secret_value()

    def model_for(self, role: str) -> str:
        """Configured model ID for a role ("vlm", "agent", "audio")."""
        return getattr(self, f"nebius_{role}_model")


@lru_cache
def get_settings() -> Settings:
    return Settings()
