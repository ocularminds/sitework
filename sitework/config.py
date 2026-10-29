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
    # Narrow decision:enforce key for ENFORCEMENT/PARALLEL evaluations and grants.
    decionis_enforce_api_key: SecretStr | None = None
    # Policy authoring only. Never use this credential as the gateway runtime key.
    decionis_policy_api_key: SecretStr | None = None
    agentsafe_tenant_key: SecretStr | None = None
    decionis_org_id: str = ""
    decionis_api_base: str = "https://api.decionis.com"
    decionis_gateway_url: str = "https://sitework.decionisedge.com"
    # A different tenant needs its own ingress key; never switch automatically.
    decionis_gateway_fallback: str = ""
    decionis_mode: Literal["live", "mock"] = "live"
    # Gate calls: Agent-Safe Intent v1 through the dci gateway. The intent's tenant_id is
    # the organization UUID (DECIONIS_ORG_ID); a granted ALLOW is claimed before going green.
    decionis_gate_route: str = "/v1/authority/enforce-and-bind"
    decionis_claim_route: str = "/v1/execution/consume-token"
    decionis_gate_mode: Literal["SHADOW", "PARALLEL", "ENFORCEMENT"] = "ENFORCEMENT"
    decionis_decision_type: str = ""  # sets the intent's policy_projection when non-empty
    decionis_actor_id: str = "sitework-inspector"
    decionis_intent_ttl_s: int = 120

    # SiteWork runtime.
    sitework_source: str = "0"  # camera index, or a video file to replay
    sitework_samples: int = 3  # frames measured per inspection
    sitework_audio_source: str = ""  # "mic", "mic:<n>", a file; empty: the replayed clip's own track or mic
    sitework_audio_seconds: float = 3.0  # recorded around the join when using a microphone
    audio_onset_ratio: float = 8.0  # DSP seat click: starting values, to calibrate on bench recordings
    audio_centroid_hz: float = 1500.0
    sitework_jurisdiction: str = "US"
    fiducial_mm: float = 40.0  # printed ArUco DICT_4X4_50 side length
    data_dir: Path = ROOT / "data"


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
