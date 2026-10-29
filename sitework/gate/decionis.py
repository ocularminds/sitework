"""Decionis HTTP transport: reachability, credentials and authenticated gateway calls."""

import httpx
from pydantic import BaseModel

from sitework.config import Settings


class Probe(BaseModel):
    """One HTTP probe against a Decionis endpoint."""

    url: str
    status: int | None = None
    body: dict | str | None = None
    error: str | None = None
    agentsafe_execution: str | None = None

    @property
    def code(self) -> str:
        """Machine code from an error body (`error` or `code`), if any."""
        if isinstance(self.body, dict):
            return str(self.body.get("code") or self.body.get("error") or "")
        return ""

    def summary(self) -> str:
        if self.error:
            return f"{self.url} -> {self.error}"
        tail = f" {self.code}" if self.code else ""
        return f"{self.url} -> {self.status}{tail}"


class DecionisClient:
    """Talks to the Decionis API and the hosted AgentSafe gateway over HTTPS."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        key = settings.decionis_api_key
        self._read_key = key.get_secret_value() if key else ""
        self.credential_env_var = "DECIONIS_API_KEY"
        if settings.decionis_gate_mode != "SHADOW" and settings.decionis_enforce_api_key:
            key = settings.decionis_enforce_api_key
            self.credential_env_var = "DECIONIS_ENFORCE_API_KEY"
        self._key = key.get_secret_value() if key else ""
        tenant_key = settings.agentsafe_tenant_key
        self._tenant_key = tenant_key.get_secret_value() if tenant_key else ""
        self._http = httpx.Client(timeout=settings.request_timeout, transport=transport)

    @property
    def has_key(self) -> bool:
        return bool(self._key)

    @property
    def has_tenant_key(self) -> bool:
        return bool(self._tenant_key)

    def close(self) -> None:
        self._http.close()

    def health(self) -> Probe:
        """Public liveness: `GET /v1/health` needs no key."""
        return self._request("GET", f"{self._settings.decionis_api_base.rstrip('/')}/v1/health")

    def key_check(self) -> Probe:
        """Check the credential used by gate calls in the configured mode."""
        url = f"{self._settings.decionis_api_base.rstrip('/')}/v1/auth/credential-context"
        if not self.has_key:
            return Probe(url=url, error=f"{self.credential_env_var} is not set")
        return self._request(
            "POST", url, headers={"Authorization": f"Bearer {self._key}"}, json={}
        )

    def policy_bundle(self) -> Probe:
        """Read workspace mode limits with the read key, outside the grant-only credential."""
        url = f"{self._settings.decionis_api_base.rstrip('/')}/v1/edge/policy-bundles/current"
        if not self._read_key:
            return Probe(url=url, error="DECIONIS_API_KEY is required to read workspace mode limits")
        return self._request("GET", url, headers={"Authorization": f"Bearer {self._read_key}"},
                             params={"ttl_seconds": 60})

    def gateway(self, base: str) -> Probe:
        """Verify the selected tenant's routing to the public authority health endpoint."""
        url = f"{base.rstrip('/')}/v1/health"
        if base.rstrip('/') != self._settings.decionis_gateway_url.rstrip('/'):
            return Probe(url=url, error="A different gateway requires its own tenant key")
        if not self.has_tenant_key:
            return Probe(url=url, error="AGENTSAFE_TENANT_KEY is not set")
        return self._request("GET", url, headers={"AgentSafe-Tenant-Key": self._tenant_key})

    def post(self, route: str, body: dict, idempotency_key: str | None = None) -> Probe:
        """POST through the selected gateway with ingress and mode-appropriate credentials.

        Authority intents carry their retry identity in `context.idempotency_key`, inside the
        hash, so they are sent without an `Idempotency-Key` header.
        """
        url = f"{self._settings.decionis_gateway_url.rstrip('/')}{route}"
        if not (self.has_key and self.has_tenant_key):
            return Probe(url=url, error=f"{self.credential_env_var} and AGENTSAFE_TENANT_KEY are required")
        headers = {"Authorization": f"Bearer {self._key}", "AgentSafe-Tenant-Key": self._tenant_key}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return self._request("POST", url, headers=headers, json=body)

    def key_accepted(self, probe: Probe) -> bool:
        body = probe.body
        return (
            probe.status == 200
            and isinstance(body, dict)
            and body.get("authority") == "org_api_key"
            and bool(body.get("api_key_id"))
            and bool(self._settings.decionis_org_id)
            and body.get("org_id") == self._settings.decionis_org_id
        )

    def _request(self, method: str, url: str, **kwargs) -> Probe:
        try:
            res = self._http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            return Probe(url=url, error=f"{type(exc).__name__}: {exc}")
        try:
            body: dict | str = res.json()
        except ValueError:
            body = res.text[:200]
        return Probe(
            url=url, status=res.status_code, body=body,
            agentsafe_execution=res.headers.get("agentsafe-execution"),
        )
