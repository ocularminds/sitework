import json
from types import SimpleNamespace

import numpy as np
import pytest

from sitework.capture import Frame
from sitework.perceive.views import DeckingView
from sitework.perceive.vlm import VisionError, VisionModel, parse_json

GOOD = {"boards": [{"edges": [[[10, 10], [200, 10]], [[10, 40], [200, 40]]]},
                   {"edges": [[[10, 45], [200, 46]], [[10, 75], [200, 76]]]}], "confidence": 0.8}


class FakeClient:
    """Mimics `client.chat.completions.create`, replying with queued texts."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self.replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def frame() -> Frame:
    return Frame(np.zeros((240, 320, 3), np.uint8), 0)


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('result: {"a": {"b": 2}} done') == {"a": {"b": 2}}
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_valid_reply_is_converted_from_the_0_to_1000_grid_to_pixels():
    client = FakeClient([json.dumps(GOOD)])
    view = VisionModel(client, "acme/vl").locate(frame(), DeckingView)  # frame is 320x240
    assert len(view.boards) == 2 and view.confidence == 0.8
    assert view.boards[0].edges[0] == [[3.2, 2.4], [64.0, 2.4]]
    content = client.calls[0]["messages"][0]["content"]
    assert content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "0 to 1000 grid" in content[1]["text"] and client.calls[0]["temperature"] == 0


@pytest.mark.parametrize("bad", [
    "not json",
    json.dumps({**GOOD, "notes": "free text is not allowed"}),
    json.dumps({**GOOD, "boards": GOOD["boards"][:1]}),
    json.dumps({**GOOD, "boards": [{"edges": [[[10, 10], [1200, 10]], [[10, 40], [200, 40]]]}] * 2}),
])
def test_one_bad_reply_is_retried_with_the_reason(bad):
    client = FakeClient([bad, json.dumps(GOOD)])
    VisionModel(client, "acme/vl").locate(frame(), DeckingView)
    assert len(client.calls) == 2
    assert "rejected" in client.calls[1]["messages"][-1]["content"]


def test_two_bad_replies_raise():
    client = FakeClient(["nope", "still nope"])
    with pytest.raises(VisionError, match="after retry"):
        VisionModel(client, "acme/vl").locate(frame(), DeckingView)


def test_missing_model_id_is_an_error():
    with pytest.raises(VisionError, match="nebius_vlm_model"):
        VisionModel(FakeClient([]), "")


def test_constrained_decoding_and_thinking_off_are_sent_to_the_server():
    client = FakeClient([json.dumps(GOOD)])
    VisionModel(client, "acme/vl").locate(frame(), DeckingView)
    call = client.calls[0]
    assert call["response_format"]["type"] == "json_schema"
    assert call["response_format"]["json_schema"]["name"] == "deckingview"
    assert call["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
    assert call["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_thinking_on_and_unconstrained_send_neither_option():
    client = FakeClient([json.dumps(GOOD)])
    VisionModel(client, "acme/vl", thinking=True, constrained=False).locate(frame(), DeckingView)
    assert "response_format" not in client.calls[0] and "extra_body" not in client.calls[0]
