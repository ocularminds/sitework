import httpx
import pytest

from sitework.config import Settings
from sitework.gate.decionis import DecionisClient, Probe
from sitework.health import DecionisCheck


ORG = "124e5022-6eee-4717-ab65-a03899db6237"
GATEWAY = "https://dci.decionisedge.com"


def settings(**overrides):
    return Settings(_env_file=None, **{
        "decionis_api_key": "test-workspace-key",
        "agentsafe_tenant_key": "test-tenant-key",
        "decionis_org_id": ORG,
        "decionis_gateway_url": GATEWAY,
        **overrides,
    })


def identity(org_id=ORG):
    return {"authority": "org_api_key", "org_id": org_id, "api_key_id": "test-key-id"}


def test_credentials_stay_on_their_intended_requests():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=identity())

    client = DecionisClient(settings(), transport=httpx.MockTransport(respond))
    client.health()
    assert client.key_accepted(client.key_check())
    client.gateway(GATEWAY)
    public, credential, gateway = requests
    assert "authorization" not in public.headers
    assert "agentsafe-tenant-key" not in public.headers
    assert credential.method == "POST"
    assert str(credential.url) == "https://api.decionis.com/v1/auth/credential-context"
    assert credential.headers["authorization"] == "Bearer test-workspace-key"
    assert "agentsafe-tenant-key" not in credential.headers
    assert gateway.headers["agentsafe-tenant-key"] == "test-tenant-key"
    assert "authorization" not in gateway.headers
    client.close()


@pytest.mark.parametrize("status", [301, 401, 403, 404, 421, 500, 503])
def test_http_failures_never_count_as_accepted_credentials(status):
    client = DecionisClient(settings())
    assert not client.key_accepted(Probe(url="https://api.decionis.com", status=status, body=identity()))
    client.close()


@pytest.mark.parametrize("body", [{}, {"ok": True}, identity("another-workspace"), {**identity(), "authority": "onboarding"}])
def test_success_status_requires_the_expected_workspace_identity(body):
    client = DecionisClient(settings())
    assert not client.key_accepted(Probe(url="https://api.decionis.com", status=200, body=body))
    client.close()


def test_missing_key_and_different_gateway_make_no_request():
    def unexpected(request):
        pytest.fail(f"Unexpected request to {request.url}")

    transport = httpx.MockTransport(unexpected)
    missing = DecionisClient(settings(agentsafe_tenant_key=None), transport=transport)
    assert "AGENTSAFE_TENANT_KEY" in missing.gateway(GATEWAY).error
    missing.close()
    configured = DecionisClient(settings(), transport=transport)
    assert "different gateway" in configured.gateway("https://sitework.decionisedge.com").error
    configured.close()


@pytest.mark.parametrize("gateway_status,execution,blocked", [
    (200, "PASSTHROUGH", False), (503, "NOT_FORWARDED", True), (200, None, True),
])
def test_doctor_verifies_only_the_selected_gateway(gateway_status, execution, blocked):
    hosts = []

    def respond(request):
        hosts.append(request.url.host)
        if request.url.path == "/v1/auth/credential-context":
            return httpx.Response(200, json=identity())
        if request.url.host == "dci.decionisedge.com":
            headers = {"agentsafe-execution": execution} if execution else {}
            return httpx.Response(gateway_status, json={"ok": True}, headers=headers)
        return httpx.Response(200, json={"ok": True})

    config = settings(decionis_gateway_fallback="https://sitework.decionisedge.com")
    client = DecionisClient(config, transport=httpx.MockTransport(respond))
    result = DecionisCheck(config, client).run()
    assert result.ok is not blocked
    assert "sitework.decionisedge.com" not in hosts
    client.close()
