import io
import wave

import pytest

from sitework.nebius import ROLES, ModelCatalog, Role, _tone_wav

# Fixture IDs only; real IDs come from Token Factory `GET /models`.
IDS = [
    "acme/Nemotron-Nano-12B-v2-VL",
    "acme/Nemotron-3-Super-test",
    "acme/Nemotron-3-Nano-Omni-test",
    "acme/Llama-vision-test",
    "acme/nemotron-mini",
]


def role(name: str) -> Role:
    return next(r for r in ROLES if r.name == name)


@pytest.mark.parametrize("name,expected", [
    ("vlm", ["acme/Nemotron-Nano-12B-v2-VL"]),
    ("agent", ["acme/Nemotron-3-Super-test"]),
    ("audio", ["acme/Nemotron-3-Nano-Omni-test"]),
])
def test_roles_pick_only_their_candidates(name, expected):
    assert ModelCatalog(IDS).candidates(role(name)) == expected


def test_role_terms_match_whole_tokens_not_substrings():
    assert not role("vlm").matches("acme/nemotron-level-test")


def test_catalog_deduplicates_and_supports_membership():
    catalog = ModelCatalog(IDS + IDS[:1])
    assert len(catalog) == len(IDS)
    assert IDS[0] in catalog
    assert "acme/unknown" not in catalog


def test_tone_is_a_valid_half_second_mono_wav():
    with wave.open(io.BytesIO(_tone_wav())) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() == 8000
