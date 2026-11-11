import json

import pytest
from pydantic import ValidationError

from c2a.planner import Storyboard, load_concepts

SCENE = {"title": "Intro", "visual": "A right triangle appears in the center.", "narration": "Hi."}


def test_valid_storyboard():
    sb = Storyboard.model_validate_json(json.dumps({"scenes": [SCENE, SCENE, SCENE]}))
    assert len(sb.scenes) == 3


@pytest.mark.parametrize("bad", [
    {"scenes": [SCENE]},                                   # too few scenes
    {"scenes": [SCENE] * 7},                               # too many
    {"scenes": [{"title": "x", "visual": "short", "narration": "y"}] * 3},   # visual too vague
    {"scenes": [{"title": "x", "narration": "y"}] * 3},    # missing field
    {"steps": [SCENE] * 3},                                # wrong key
])
def test_invalid_storyboards(bad):
    with pytest.raises(ValidationError):
        Storyboard.model_validate(bad)


def test_concepts_file_is_well_formed():
    concepts = load_concepts()
    ids = [c["id"] for c in concepts]
    assert len(ids) == len(set(ids)), "duplicate concept ids"
    for c in concepts:
        assert {"id", "name", "tier", "description"} <= c.keys()
        assert c["tier"] in {"concrete", "structural", "abstract"}
