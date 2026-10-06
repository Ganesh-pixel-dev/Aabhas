import time

from aabhas.store import Store


def test_clip_retention_and_false_alarm_delete(tmp_path):
    s = Store(tmp_path)
    a = s.add_alert("c", "loc", 1, 0.0, 30.0, "ALERT")
    (s.clip_dir(a) / "00000.jpg").write_bytes(b"x")
    s.update_alert(a, clip_frames=1)
    assert s.purge_old_clips(72) == 0
    s.update_alert(a, wall=time.time() - 80 * 3600)
    assert s.purge_old_clips(72) == 1
    assert not (tmp_path / "alerts" / str(a) / "clip").exists()
    assert s.alert(a)["clip_frames"] == 0
