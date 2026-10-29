import httpx
import pytest
import json
from base64 import urlsafe_b64encode

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


def identity(org_id=ORG, scopes=None):
    return {"authority": "org_api_key", "org_id": org_id, "api_key_id": "test-key-id",
            "scopes": ["decision:run", "decision:enforce", "policy:read"] if scopes is None else scopes}


def mode_metadata(maximum="ENFORCEMENT", org_id=ORG, reason=None):
    claims = {"aud": org_id, "max_mode": maximum, "max_mode_reason": reason}
    payload = urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return {"signed_bundle": f"test.{payload}.signature"}


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
        if request.url.path == "/v1/edge/policy-bundles/current":
            return httpx.Response(200, json=mode_metadata())
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


@pytest.mark.parametrize("mode", ["ENFORCEMENT", "PARALLEL"])
def test_enforcement_key_handles_evaluations_and_claims_while_reads_keep_read_key(mode):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={})

    client = DecionisClient(settings(decionis_gate_mode=mode,
                                    decionis_enforce_api_key="test-enforcement-key"),
                            transport=httpx.MockTransport(respond))
    client.key_check()
    client.post("/v1/authority/enforce-and-bind", {})
    client.post("/v1/execution/consume-token", {})
    client.policy_bundle()
    assert [r.headers["authorization"] for r in requests] == [
        "Bearer test-enforcement-key", "Bearer test-enforcement-key",
        "Bearer test-enforcement-key", "Bearer test-workspace-key"]
    assert all(r.headers["agentsafe-tenant-key"] == "test-tenant-key" for r in requests[1:3])
    assert "agentsafe-tenant-key" not in requests[-1].headers
    client.close()


def test_explicit_shadow_mode_uses_the_shadow_credential():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=identity(scopes=["decision:run"]))

    client = DecionisClient(settings(decionis_gate_mode="SHADOW",
                                    decionis_enforce_api_key="test-enforcement-key"),
                            transport=httpx.MockTransport(respond))
    client.key_check()
    client.post("/v1/authority/enforce-and-bind", {})
    assert all(r.headers["authorization"] == "Bearer test-workspace-key" for r in requests)
    client.close()


@pytest.mark.parametrize("mode,scopes,blocked", [
    ("SHADOW", ["decision:run"], False),
    ("SHADOW", ["decision:shadow"], False),
    ("ENFORCEMENT", ["decision:run"], True),
    ("PARALLEL", ["decision:run"], True),
    ("ENFORCEMENT", ["decision:enforce"], False),
    ("ENFORCEMENT", ["decision:write"], False),
    ("ENFORCEMENT", ["decision:*"], False),
    ("ENFORCEMENT", ["policy:write"], True),
    ("ENFORCEMENT", [], True),
])
def test_readiness_requires_scope_for_the_selected_mode(mode, scopes, blocked):
    def respond(request):
        if request.url.path == "/v1/auth/credential-context":
            return httpx.Response(200, json=identity(scopes=scopes))
        if request.url.path == "/v1/edge/policy-bundles/current":
            return httpx.Response(200, json=mode_metadata())
        return httpx.Response(200, json={"ok": True}, headers={"agentsafe-execution": "PASSTHROUGH"})

    config = settings(decionis_gate_mode=mode)
    client = DecionisClient(config, transport=httpx.MockTransport(respond))
    result = DecionisCheck(config, client).run()
    assert result.ok is not blocked
    assert mode in result.name
    if blocked:
        assert any("cannot run" in b for b in result.blockers)
    client.close()


@pytest.mark.parametrize("mode,blocked", [("SHADOW", False), ("ENFORCEMENT", True), ("PARALLEL", True)])
def test_enforcement_scope_does_not_hide_an_unclaimed_workspace(mode, blocked):
    def respond(request):
        if request.url.path == "/v1/auth/credential-context":
            return httpx.Response(200, json=identity(scopes=["decision:enforce"]))
        if request.url.path == "/v1/edge/policy-bundles/current":
            return httpx.Response(200, json=mode_metadata("SHADOW", reason="PROVISIONAL_WORKSPACE_SHADOW_ONLY"))
        return httpx.Response(200, json={"ok": True}, headers={"agentsafe-execution": "PASSTHROUGH"})

    config = settings(decionis_gate_mode=mode)
    client = DecionisClient(config, transport=httpx.MockTransport(respond))
    result = DecionisCheck(config, client).run()
    assert result.ok is not blocked
    if blocked:
        assert any("PROVISIONAL_WORKSPACE_SHADOW_ONLY" in b for b in result.blockers)
    client.close()


@pytest.mark.parametrize("metadata", [mode_metadata(org_id="other-workspace"),
                                     mode_metadata(maximum="UNKNOWN"), {"signed_bundle": "bad"}, {}])
def test_unverified_workspace_mode_cannot_pass_readiness(metadata):
    def respond(request):
        if request.url.path == "/v1/auth/credential-context":
            return httpx.Response(200, json=identity())
        if request.url.path == "/v1/edge/policy-bundles/current":
            return httpx.Response(200, json=metadata)
        return httpx.Response(200, json={"ok": True}, headers={"agentsafe-execution": "PASSTHROUGH"})

    config = settings()
    client = DecionisClient(config, transport=httpx.MockTransport(respond))
    result = DecionisCheck(config, client).run()
    assert not result.ok
    assert any("mode claims" in b for b in result.blockers)
    client.close()
