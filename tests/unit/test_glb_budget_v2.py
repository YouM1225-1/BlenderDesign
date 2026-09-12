import pytest

from acceptance.glb_budget import measure_glb
from tests.unit.interchange_support import make_budget_fixture, policy


def test_budget_counts_each_instance_separately(tmp_path):
    path = tmp_path / "scene.glb"
    make_budget_fixture(path, 2)
    limits = policy(tmp_path)["limits"]
    limits["max_rendered_triangles"] = 1
    measured = measure_glb(path, limits)
    assert measured["stored_triangles"] == 1 and measured["rendered_triangles"] == 2
    assert measured["draw_calls"] == 2 and measured["exceeded"] == ["rendered_triangles"]


def test_short_glb_and_wrong_length_are_rejected(tmp_path):
    path = tmp_path / "bad.glb"
    path.write_bytes(b"glTF")
    with pytest.raises(ValueError, match="header"):
        measure_glb(path, policy(tmp_path)["limits"])
    make_budget_fixture(path, 1)
    path.write_bytes(path.read_bytes() + b"xxxx")
    with pytest.raises(ValueError, match="header"):
        measure_glb(path, policy(tmp_path)["limits"])


def test_budget_rejects_external_and_data_uris(tmp_path):
    path = tmp_path / "uri.glb"
    make_budget_fixture(path, 1)
    raw = path.read_bytes()
    json_end = 20 + int.from_bytes(raw[12:16], "little")
    import json
    document = json.loads(raw[20:json_end])
    document["buffers"] = [{"uri": "data:application/octet-stream;base64,AA=="}]
    encoded = json.dumps(document).encode()
    encoded += b" " * ((-len(encoded)) % 4)
    path.write_bytes(
        raw[:8]
        + (20 + len(encoded)).to_bytes(4, "little")
        + len(encoded).to_bytes(4, "little")
        + raw[16:20]
        + encoded
    )
    with pytest.raises(ValueError, match="URI"):
        measure_glb(path, policy(tmp_path)["limits"])
