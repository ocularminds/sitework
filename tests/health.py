from sitework.config import Settings
from sitework.health import TavilyCheck, TokenFactoryCheck
from sitework.ground.web import WebResult
from sitework.nebius import ModelCatalog

VLM = "acme/Nemotron-Nano-12B-v2-VL"
AGENT = "acme/Nemotron-3-Super-test"


class FakeFactory:
    def __init__(self, ids):
        self.ids = ids
        self.audio_calls = []

    def catalog(self):
        return ModelCatalog(self.ids)

    def accepts_audio(self, model):
        self.audio_calls.append(model)
        return False, "BadRequestError: audio not supported"


class FakeWeb:
    def __init__(self, results):
        self.results = results

    def search(self, query, domains, max_results=5):
        return self.results


def offline(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_missing_keys_become_blockers_not_crashes():
    settings = offline(nebius_api_key=None, tavily_api_key=None)
    factory, tavily = TokenFactoryCheck(settings).run(), TavilyCheck(settings).run()
    assert "NEBIUS_API_KEY" in factory.blockers[0]
    assert "TAVILY_API_KEY" in tavily.blockers[0]
    assert not factory.ok and not tavily.ok


def test_unrecorded_model_ids_block_until_written_to_config():
    result = TokenFactoryCheck(offline(), FakeFactory([VLM, AGENT])).run()
    assert not result.ok
    assert any("nebius_vlm_model" in b for b in result.blockers)
    assert any("nebius_agent_model" in b for b in result.blockers)
    assert any("fallback is Audio Flamingo 3" in d for d in result.detail)


def test_recorded_ids_that_are_listed_pass():
    settings = offline(nebius_vlm_model=VLM, nebius_agent_model=AGENT)
    assert TokenFactoryCheck(settings, FakeFactory([VLM, AGENT])).run().ok


def test_recorded_id_missing_from_models_blocks():
    settings = offline(nebius_vlm_model="acme/gone", nebius_agent_model=AGENT)
    result = TokenFactoryCheck(settings, FakeFactory([VLM, AGENT])).run()
    assert result.blockers == ["vlm: configured ID 'acme/gone' is not in /models"]


def test_audio_candidate_is_probed_and_rejection_reported():
    omni = "acme/Nemotron-3-Nano-Omni-test"
    factory = FakeFactory([VLM, AGENT, omni])
    settings = offline(nebius_vlm_model=VLM, nebius_agent_model=AGENT)
    result = TokenFactoryCheck(settings, factory).run()
    assert factory.audio_calls == [omni]
    assert any("rejected input_audio" in d for d in result.detail)
    assert result.ok  # audio has a self-hosted fallback, so it never blocks P0


def test_tavily_without_allowlisted_results_blocks():
    assert not TavilyCheck(offline(), FakeWeb([])).run().ok
    hit = WebResult(url="https://www.osha.gov/laws-regs/1926.652")
    assert TavilyCheck(offline(), FakeWeb([hit])).run().ok
