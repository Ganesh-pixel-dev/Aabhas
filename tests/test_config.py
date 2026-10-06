import pytest

from aabhas.config import Thresholds, load_settings


def test_override_and_unknown_key():
    assert Thresholds().with_overrides({"down_seconds": 5}).down_seconds == 5
    with pytest.raises(ValueError):
        Thresholds().with_overrides({"down_secs": 5})


def test_per_camera_override(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("thresholds: {down_seconds: 20}\ncameras:\n  - {id: a, name: A, location: X, source: 0}\n"
                 "  - {id: b, name: B, location: Y, source: 0, thresholds: {down_seconds: 45}}\n")
    s = load_settings(f)
    assert [c.thresholds.down_seconds for c in s.cameras] == [20, 45]
