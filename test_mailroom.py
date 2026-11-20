import subprocess
from datetime import date
from pathlib import Path

from mailroom.checks import check_issue, check_subject
from mailroom.subscribers import joined_since, read_subscribers


def run(*args: str) -> list[str]:
    result = subprocess.run(
        ["uv", "run", "mailroom", *args], capture_output=True, text=True
    )
    assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
    return result.stdout.splitlines()


def test_subscribers_reports_total_of_24() -> None:
    assert "Total: 24" in run("subscribers")


def test_subscribers_reports_8_tea_curious() -> None:
    assert "tea-curious: 8" in run("subscribers")


def test_subscribers_reports_8_gift_buyers() -> None:
    assert "gift-buyers: 8" in run("subscribers")


def test_subscribers_reports_8_daily_drinkers() -> None:
    assert "daily-drinkers: 8" in run("subscribers")


def test_subscribers_counts_7_joined_in_last_30_days() -> None:
    lines = run("subscribers", "--since-days", "30", "--run-date", "2026-11-20")
    assert "Joined in last 30 days: 7" in lines


def test_joined_since_counts_7_joined_in_30_days_up_to_date_2026_11_20() -> None:
    rows = read_subscribers()
    assert len(joined_since(rows, date(2026, 11, 20), 30)) == 7


def test_next_send_from_2026_11_20_is_2026_12_07() -> None:
    assert run("next-send", "--run-date", "2026-11-20") == ["Next send: 2026-12-07"]


def test_next_send_on_a_send_day_moves_to_the_following_send_2027_01_04() -> None:
    assert run("next-send", "--run-date", "2026-12-07") == ["Next send: 2027-01-04"]


def issue(subject_line: str | None) -> str:
    """Build issue text. Pass None for an issue with no Subject line at all."""
    body = "Hello, Steep Clubbers.\n"
    if subject_line is None:
        return body
    return f"Subject: {subject_line}\n\n{body}"


def test_check_subject_short_subject_has_no_problems() -> None:
    assert check_subject(issue("The Steep Club opens Monday")) == []


def test_check_subject_of_exactly_50_characters_has_no_problems() -> None:
    subject = "Your Steep Club box ships on Monday with new teas."
    assert len(subject) == 50
    assert check_subject(issue(subject)) == []


def test_check_subject_of_51_characters_is_too_long() -> None:
    subject = "Your Steep Club box ships on Monday with fresh teas"
    assert len(subject) == 51
    assert check_subject(issue(subject)) == ["too long"]


def test_subject_length_counts_code_points_like_len_so_thumbs_up_with_skin_tone_is_2() -> None:
    subject = "\U0001F44D\U0001F3FD Thanks for joining"  # 👍🏽 = thumbs up + skin tone
    assert len(subject) == 21
    assert check_subject(issue(subject)) == []


def test_check_subject_of_51_code_points_but_50_visible_characters_is_too_long() -> None:
    # 👍🏽 shows as 1 character but is 2 code points, so this is 51 by len().
    subject = "\U0001F44D\U0001F3FD Your Steep Club box ships Monday with fresh teas"
    assert len(subject) == 51
    assert check_subject(issue(subject)) == ["too long"]


def test_check_subject_empty_is_one_problem_empty() -> None:
    assert check_subject(issue("")) == ["empty"]


def test_check_subject_of_only_spaces_is_one_problem_empty() -> None:
    assert check_subject(issue("   ")) == ["empty"]


def test_check_subject_missing_is_one_problem_missing() -> None:
    assert check_subject(issue(None)) == ["missing"]


ISSUE_01 = Path(__file__).parent / "issues" / "issue-01.md"


def issue_01_with(old: str, new: str) -> str:
    """issue-01 with `old` replaced by `new`; fails loudly if `old` is not there."""
    text = ISSUE_01.read_text()
    assert old in text, f"{old!r} not found in issue-01.md"
    return text.replace(old, new)


def test_check_issue_issue_01_has_no_problems() -> None:
    assert check_issue(ISSUE_01.read_text()) == []


def test_check_issue_preview_of_91_characters_is_one_problem() -> None:
    preview = "Preview: " + "a" * 91
    text = issue_01_with(
        "Preview: Your monthly tea box, chosen by our blenders. Founding members get the first box free.",
        preview,
    )
    assert len(check_issue(text)) == 1


def test_check_issue_without_first_name_is_one_problem() -> None:
    assert len(check_issue(issue_01_with("{{first_name}}", "there"))) == 1


def test_check_issue_with_two_links_is_one_problem() -> None:
    second = "[Read more](https://kettlebird.example/about)"
    text = issue_01_with("Steep well,", f"{second}\n\nSteep well,")
    assert len(check_issue(text)) == 1


def test_check_issue_second_link_starting_http_still_counts_as_a_link() -> None:
    second = "[Read more](http://kettlebird.example/about)"
    text = issue_01_with("Steep well,", f"{second}\n\nSteep well,")
    assert len(check_issue(text)) == 1


def test_check_issue_without_footer_and_without_greeting_is_two_problems() -> None:
    footer = (
        "You're getting this because you joined the Kettlebird Tea waitlist.\n"
        "Kettlebird Tea, {{company_address}} · Unsubscribe: {{unsubscribe_url}}\n"
    )
    text = issue_01_with(footer, "")
    text = text.replace("{{first_name}}", "there")
    assert len(check_issue(text)) == 2


def test_check_command_on_issue_01_prints_ok() -> None:
    assert run("check", "issues/issue-01.md") == ["OK"]


def test_check_command_prints_each_problem_on_its_own_line(tmp_path: Path) -> None:
    text = issue_01_with("{{first_name}}", "there").replace(
        "Unsubscribe: {{unsubscribe_url}}", ""
    )
    bad_issue = tmp_path / "bad-issue.md"
    bad_issue.write_text(text)
    lines = run("check", str(bad_issue))
    assert len(lines) == 2
    assert "OK" not in lines
