import subprocess


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
