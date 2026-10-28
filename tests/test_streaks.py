from datetime import date, timedelta

from app.services.streaks import compute_streak

TODAY = date(2026, 10, 24)


def days_ago(*offsets: int) -> list[date]:
    return [TODAY - timedelta(days=n) for n in offsets]


def test_no_logs():
    info = compute_streak([], TODAY)
    assert (info.current_streak, info.longest_streak) == (0, 0)
    assert info.last_completed_date is None and info.completed_today is False


def test_only_today():
    info = compute_streak(days_ago(0), TODAY)
    assert (info.current_streak, info.longest_streak, info.completed_today) == (1, 1, True)


def test_consecutive_run_ending_today():
    info = compute_streak(days_ago(0, 1, 2), TODAY)
    assert (info.current_streak, info.longest_streak) == (3, 3)


def test_streak_stays_alive_until_the_day_ends():
    info = compute_streak(days_ago(1, 2, 3), TODAY)  # nothing logged yet today
    assert info.current_streak == 3
    assert info.completed_today is False


def test_missing_a_whole_day_breaks_the_current_streak():
    info = compute_streak(days_ago(2, 3, 4), TODAY)
    assert info.current_streak == 0
    assert info.longest_streak == 3
    assert info.last_completed_date == TODAY - timedelta(days=2)


def test_longest_remembers_an_earlier_better_run():
    info = compute_streak(days_ago(0, 1, 5, 6, 7, 8), TODAY)
    assert (info.current_streak, info.longest_streak) == (2, 4)


def test_duplicates_and_order_do_not_matter():
    info = compute_streak(days_ago(0, 2, 1, 0, 2), TODAY)
    assert info.current_streak == 3


def test_year_boundary():
    dates = [date(2026, 12, 31), date(2027, 1, 1), date(2027, 1, 2)]
    assert compute_streak(dates, date(2027, 1, 2)).current_streak == 3


def test_leap_day():
    dates = [date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1)]
    assert compute_streak(dates, date(2028, 3, 1)).current_streak == 3


def test_a_log_dated_in_the_future_does_not_break_the_streak():
    info = compute_streak(days_ago(1, 0, -1), TODAY)  # timezone moved backwards
    assert info.current_streak == 3
    assert info.completed_today is False


def test_a_single_missed_day_splits_the_run():
    info = compute_streak(days_ago(0, 1, 3, 4), TODAY)  # day 2 is missing
    assert (info.current_streak, info.longest_streak) == (2, 2)
