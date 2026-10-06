from aabhas.fall_machine import State
from tests.scripts import LIE, SIT, STAND, Run, standing_then_fall


def test_standing_person_stays_upright():
    r = Run()
    r.feed(STAND, 8, 60)
    assert r.state == State.UPRIGHT and r.log == []


def test_fall_then_down_then_alert_when_nobody_helps():
    r = standing_then_fall()
    assert r.state == State.FALL
    r.feed(LIE, 85, 2.5)
    assert r.state == State.DOWN
    r.feed(LIE, 85, 20)
    assert r.state == State.DOWN            # still counting, not yet 30 s
    r.feed(LIE, 85, 12)
    assert r.state == State.ALERT
    assert r.states() == [State.FALL, State.DOWN, State.ALERT]


def test_alert_time_counts_from_start_of_fall():
    r = standing_then_fall(down_seconds=10)
    r.feed(LIE, 85, 12)
    alert = [tr for tr in r.log if tr.dst == State.ALERT][0]
    fall = [tr for tr in r.log if tr.dst == State.FALL][0]
    assert 9.5 <= alert.t - fall.info["fall_t"] <= 10.5


def test_configurable_down_seconds():
    r = standing_then_fall(down_seconds=5)
    r.feed(LIE, 85, 6)
    assert r.state == State.ALERT


def test_help_arrives_while_down_means_no_alert():
    r = standing_then_fall()
    r.feed(LIE, 85, 10)
    r.feed(LIE, 85, 4, helper_s=4)
    assert r.state == State.BEING_HELPED
    r.feed(LIE, 85, 40, helper_s=40)
    assert State.ALERT not in r.states()


def test_help_arrives_after_alert_downgrades_it():
    r = standing_then_fall()
    r.feed(LIE, 85, 35)
    assert r.state == State.ALERT
    r.feed(LIE, 85, 4, helper_s=4)
    assert r.state == State.BEING_HELPED


def test_helper_who_leaves_returns_to_down_and_alerts_if_overdue():
    r = standing_then_fall()
    r.feed(LIE, 85, 10)
    r.feed(LIE, 85, 4, helper_s=4)
    assert r.state == State.BEING_HELPED
    r.feed(LIE, 85, 3)                       # helper gone but not for help_leave_s yet
    assert r.state == State.BEING_HELPED
    r.feed(LIE, 85, 30)
    assert r.state == State.ALERT            # down for far more than 30 s by now


def test_short_help_dwell_does_not_count():
    r = standing_then_fall()
    r.feed(LIE, 85, 10)
    r.feed(LIE, 85, 2, helper_s=2.0)         # below help_dwell_s
    assert r.state == State.DOWN


def test_person_gets_up_before_alert_is_recovered_no_alert():
    r = standing_then_fall()
    r.feed(LIE, 85, 10)
    r.move(LIE, STAND, 85, 8, 1.5)
    r.feed(STAND, 8, 2.0)
    assert State.RECOVERED in r.states()
    assert State.ALERT not in r.states()
    r.feed(STAND, 8, 5)
    assert r.state == State.UPRIGHT


def test_person_gets_up_after_alert_is_recovered():
    r = standing_then_fall()
    r.feed(LIE, 85, 40)
    assert r.state == State.ALERT
    r.move(LIE, STAND, 85, 8, 1.5)
    r.feed(STAND, 8, 2.0)
    assert r.states()[-1] == State.RECOVERED


def test_stumble_and_catch_yourself_is_recovered_not_alert():
    r = standing_then_fall()
    r.move(LIE, STAND, 85, 8, 0.6)
    r.feed(STAND, 8, 2.0)
    assert State.ALERT not in r.states() and State.DOWN not in r.states()
    assert r.states()[-1] == State.RECOVERED


def test_unacknowledged_alert_escalates():
    r = standing_then_fall(escalate_after_s=60)
    r.feed(LIE, 85, 35)
    assert r.state == State.ALERT
    r.feed(LIE, 85, 50)
    assert r.state == State.ALERT
    r.feed(LIE, 85, 12)
    assert r.state == State.ESCALATED


def test_acknowledged_alert_does_not_escalate():
    r = standing_then_fall(escalate_after_s=60)
    r.feed(LIE, 85, 35)
    r.m.acknowledge()
    r.feed(LIE, 85, 200)
    assert r.state == State.ALERT


def test_dispatch_counts_as_acknowledged():
    r = standing_then_fall(escalate_after_s=60)
    r.feed(LIE, 85, 35)
    r.m.dispatch()
    r.feed(LIE, 85, 200)
    assert r.state == State.ALERT and r.m.dispatched


def test_false_alarm_silences_until_person_stands():
    r = standing_then_fall()
    r.feed(LIE, 85, 35)
    r.log += r.m.false_alarm(r.t)
    assert r.state == State.RESOLVED
    r.feed(LIE, 85, 300)
    assert r.state == State.RESOLVED
    r.move(LIE, STAND, 85, 8, 1.0)
    r.feed(STAND, 8, 2.0)
    assert r.states()[-1] == State.RECOVERED


def test_lying_down_slowly_without_a_fall_never_alerts():
    r = Run()
    r.feed(STAND, 8, 3)
    r.move(STAND, LIE, 8, 85, 6.0)           # six seconds to lie down: sleeping, not falling
    r.feed(LIE, 85, 600)
    assert State.ALERT not in r.states() and State.FALL not in r.states()
    assert r.state == State.LYING


def test_person_first_seen_lying_never_alerts():
    r = Run()
    r.feed(LIE, 85, 600)
    assert r.state == State.LYING and State.ALERT not in r.states()


def test_sitting_down_quickly_is_not_a_fall():
    r = Run()
    r.feed(STAND, 8, 3)
    r.move(STAND, SIT, 8, 12, 0.6)
    r.feed(SIT, 12, 60)
    assert r.states() == []


def test_bending_to_tie_shoelaces_is_not_a_fall():
    bend = (90.0, 120.0, 170.0, 220.0)       # torso flat-ish but hips barely drop
    r = Run()
    r.feed(STAND, 8, 3)
    r.move(STAND, bend, 8, 75, 1.5)
    r.feed(bend, 75, 6)
    r.move(bend, STAND, 75, 8, 1.5)
    r.feed(STAND, 8, 5)
    assert State.ALERT not in r.states() and State.FALL not in r.states()


def test_young_track_cannot_trigger_a_fall():
    r = Run(min_track_age_s=5.0)
    r.feed(STAND, 8, 1.0)
    r.move(STAND, LIE, 8, 85, 0.6)
    r.feed(LIE, 85, 60)
    assert State.FALL not in r.states()


def test_track_out_of_sight_while_down_still_alerts():
    r = standing_then_fall()
    r.feed(LIE, 85, 2.5)
    assert r.state == State.DOWN
    r.feed(None, None, 40, seen=False)
    assert r.state == State.ALERT


def test_second_fall_after_recovery_is_detected():
    r = standing_then_fall()
    r.move(LIE, STAND, 85, 8, 1.0)
    r.feed(STAND, 8, 6)
    r.move(STAND, LIE, 8, 85, 0.8)
    r.feed(LIE, 85, 3)
    assert r.states().count(State.FALL) == 2


def test_state_names_match_spec():
    assert {s.value for s in State} >= {"UPRIGHT", "FALL", "DOWN", "ALERT", "ESCALATED", "BEING_HELPED", "RECOVERED"}
