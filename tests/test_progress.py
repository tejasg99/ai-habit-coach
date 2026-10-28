from datetime import date

import pytest

from app.services.progress import PlanSchedule, build_daily_progress

D = date  # short alias for readability


def uniform(effective_from: date, per_day: int) -> PlanSchedule:
    return PlanSchedule(effective_from, {weekday: per_day for weekday in range(7)})


def test_no_plan_means_nothing_planned_and_no_rate():
    days = build_daily_progress(D(2026, 10, 22), D(2026, 10, 24), [], {D(2026, 10, 23): 1})
    assert [d.day for d in days] == [D(2026, 10, 22), D(2026, 10, 23), D(2026, 10, 24)]
    assert [d.planned for d in days] == [0, 0, 0]
    assert [d.completed for d in days] == [0, 1, 0]  # gaps filled with zeros
    assert all(d.completion_rate is None for d in days)


def test_single_day_window():
    days = build_daily_progress(D(2026, 10, 24), D(2026, 10, 24), [uniform(D(2026, 10, 1), 2)], {})
    assert len(days) == 1


def test_days_before_the_plan_existed_are_not_misses():
    days = build_daily_progress(D(2026, 10, 21), D(2026, 10, 24), [uniform(D(2026, 10, 23), 2)], {})
    assert [d.planned for d in days] == [0, 0, 2, 2]
    assert [d.completion_rate for d in days] == [None, None, 0.0, 0.0]


@pytest.mark.parametrize("done, rate", [(0, 0.0), (1, 0.5), (2, 1.0), (3, 1.0)])
def test_completion_rate_is_capped_at_one(done, rate):
    day = D(2026, 10, 24)
    (entry,) = build_daily_progress(day, day, [uniform(D(2026, 10, 1), 2)], {day: done})
    assert entry.completion_rate == rate


def test_planned_follows_the_weekday():
    schedule = PlanSchedule(D(2026, 10, 1), {5: 4, 6: 1})  # Saturday 4 items, Sunday 1, rest none
    days = build_daily_progress(D(2026, 10, 24), D(2026, 10, 26), [schedule], {})
    assert [d.planned for d in days] == [4, 1, 0]
    assert days[2].completion_rate is None


def test_history_uses_the_plan_that_was_active_at_the_time():
    old, new = uniform(D(2026, 10, 1), 2), uniform(D(2026, 10, 24), 5)
    days = build_daily_progress(D(2026, 10, 22), D(2026, 10, 25), [new, old], {})  # unsorted input
    assert [d.planned for d in days] == [2, 2, 5, 5]


def test_when_regenerated_twice_in_a_day_the_latest_plan_wins():
    first, second = uniform(D(2026, 10, 24), 1), uniform(D(2026, 10, 24), 3)
    (entry,) = build_daily_progress(D(2026, 10, 24), D(2026, 10, 24), [first, second], {})
    assert entry.planned == 3
