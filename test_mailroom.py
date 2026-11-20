import subprocess

from mailroom import check_subject


def run(*args):
    result = subprocess.run(
        ["uv", "run", "mailroom.py", *args], capture_output=True, text=True
    )
    assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
    return result.stdout.splitlines()


def test_subscribers_reports_total_of_24():
    assert "Total: 24" in run("subscribers")


def test_subscribers_reports_8_tea_curious():
    assert "tea-curious: 8" in run("subscribers")


def test_subscribers_reports_8_gift_buyers():
    assert "gift-buyers: 8" in run("subscribers")


def test_subscribers_reports_8_daily_drinkers():
    assert "daily-drinkers: 8" in run("subscribers")


def test_subscribers_counts_7_joined_in_last_30_days():
    lines = run("subscribers", "--since-days", "30", "--run-date", "2026-11-20")
    assert "Joined in last 30 days: 7" in lines


def test_next_send_from_2026_11_20_is_2026_12_07():
    assert run("next-send", "--run-date", "2026-11-20") == ["Next send: 2026-12-07"]


def test_next_send_on_a_send_day_moves_to_the_following_send_2027_01_04():
    assert run("next-send", "--run-date", "2026-12-07") == ["Next send: 2027-01-04"]


def issue(subject_line):
    """Build issue text. Pass None for an issue with no Subject line at all."""
    body = "Hello, Steep Clubbers.\n"
    if subject_line is None:
        return body
    return f"Subject: {subject_line}\n\n{body}"


def test_check_subject_short_subject_has_no_problems():
    assert check_subject(issue("The Steep Club opens Monday")) == []


def test_check_subject_of_exactly_50_characters_has_no_problems():
    subject = "Your Steep Club box ships on Monday with new teas."
    assert len(subject) == 50
    assert check_subject(issue(subject)) == []


def test_check_subject_of_51_characters_is_too_long():
    subject = "Your Steep Club box ships on Monday with fresh teas"
    assert len(subject) == 51
    assert check_subject(issue(subject)) == ["too long"]


def test_check_subject_empty_is_one_problem_empty():
    assert check_subject(issue("")) == ["empty"]


def test_check_subject_of_only_spaces_is_one_problem_empty():
    assert check_subject(issue("   ")) == ["empty"]


def test_check_subject_missing_is_one_problem_missing():
    assert check_subject(issue(None)) == ["missing"]
