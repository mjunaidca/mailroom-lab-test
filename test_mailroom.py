import subprocess
from datetime import date
from pathlib import Path

from mailroom.checks import check_issue, check_subject
from mailroom.issue import Issue
from mailroom.signups import read_signups
from mailroom.subscribers import joined_since, read_subscribers


def run_raw(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "mailroom", *args], capture_output=True, text=True
    )


def run(*args: str, code: int = 0) -> list[str]:
    result = run_raw(*args)
    assert result.returncode == code, f"mailroom.py failed: {result.stderr.strip()}"
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
    people = read_subscribers().good
    assert len(joined_since(people, date(2026, 11, 20), 30)) == 7


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
    assert check_subject(Issue.from_text(issue("The Steep Club opens Monday"))) == []


def test_check_subject_of_exactly_50_characters_has_no_problems() -> None:
    subject = "Your Steep Club box ships on Monday with new teas."
    assert len(subject) == 50
    assert check_subject(Issue.from_text(issue(subject))) == []


def test_check_subject_of_51_characters_is_too_long() -> None:
    subject = "Your Steep Club box ships on Monday with fresh teas"
    assert len(subject) == 51
    assert check_subject(Issue.from_text(issue(subject))) == ["too long"]


def test_subject_length_counts_code_points_like_len_so_thumbs_up_with_skin_tone_is_2() -> None:
    subject = "\U0001F44D\U0001F3FD Thanks for joining"  # 👍🏽 = thumbs up + skin tone
    assert len(subject) == 21
    assert check_subject(Issue.from_text(issue(subject))) == []


def test_check_subject_of_51_code_points_but_50_visible_characters_is_too_long() -> None:
    # 👍🏽 shows as 1 character but is 2 code points, so this is 51 by len().
    subject = "\U0001F44D\U0001F3FD Your Steep Club box ships Monday with fresh teas"
    assert len(subject) == 51
    assert check_subject(Issue.from_text(issue(subject))) == ["too long"]


def test_check_subject_empty_is_one_problem_empty() -> None:
    assert check_subject(Issue.from_text(issue(""))) == ["empty"]


def test_check_subject_of_only_spaces_is_one_problem_empty() -> None:
    assert check_subject(Issue.from_text(issue("   "))) == ["empty"]


def test_check_subject_missing_is_one_problem_missing() -> None:
    assert check_subject(Issue.from_text(issue(None))) == ["missing"]


ISSUE_01 = Path(__file__).parent / "issues" / "issue-01.md"


def issue_01_with(old: str, new: str) -> str:
    """issue-01 with `old` replaced by `new`; fails loudly if `old` is not there."""
    text = ISSUE_01.read_text()
    assert old in text, f"{old!r} not found in issue-01.md"
    return text.replace(old, new)


def test_check_issue_issue_01_has_no_problems() -> None:
    assert check_issue(Issue.from_text(ISSUE_01.read_text())) == []


def test_check_issue_preview_of_91_characters_is_one_problem() -> None:
    preview = "Preview: " + "a" * 91
    text = issue_01_with(
        "Preview: Your monthly tea box, chosen by our blenders. Founding members get the first box free.",
        preview,
    )
    assert len(check_issue(Issue.from_text(text))) == 1


def test_check_issue_without_first_name_is_one_problem() -> None:
    assert len(check_issue(Issue.from_text(issue_01_with("{{first_name}}", "there")))) == 1


def test_check_issue_with_two_links_is_one_problem() -> None:
    second = "[Read more](https://kettlebird.example/about)"
    text = issue_01_with("Steep well,", f"{second}\n\nSteep well,")
    assert len(check_issue(Issue.from_text(text))) == 1


def test_check_issue_second_link_starting_http_still_counts_as_a_link() -> None:
    second = "[Read more](http://kettlebird.example/about)"
    text = issue_01_with("Steep well,", f"{second}\n\nSteep well,")
    assert len(check_issue(Issue.from_text(text))) == 1


def test_check_issue_without_footer_and_without_greeting_is_two_problems() -> None:
    footer = (
        "You're getting this because you joined the Kettlebird Tea waitlist.\n"
        "Kettlebird Tea, {{company_address}} · Unsubscribe: {{unsubscribe_url}}\n"
    )
    text = issue_01_with(footer, "")
    text = text.replace("{{first_name}}", "there")
    assert len(check_issue(Issue.from_text(text))) == 2


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


def test_issue_01_has_one_link_https_kettlebird_example_steep_club() -> None:
    issue = Issue.from_text(ISSUE_01.read_text())
    assert issue.links == ["https://kettlebird.example/steep-club"]


def test_personalize_puts_ayesha_where_first_name_was_and_keeps_unsubscribe_url() -> None:
    personalized = Issue.from_text(ISSUE_01.read_text()).personalize("Ayesha")
    assert "Hi Ayesha," in personalized.body
    assert "{{first_name}}" not in personalized.body
    assert "{{unsubscribe_url}}" in personalized.body


NEW_SIGNUPS = "data/new-signups.csv"
RUN_DATE = "2026-11-20"


def import_line_for(first_name: str) -> str:
    lines = [l for l in run("import", NEW_SIGNUPS, "--run-date", RUN_DATE, code=1) if first_name in l]
    assert len(lines) == 1, f"expected one line for {first_name}, got {lines}"
    return lines[0]


def test_import_accepts_maria() -> None:
    assert import_line_for("Maria").startswith("accepted")


def test_import_rejects_sara_because_her_email_is_not_at_example_com() -> None:
    assert import_line_for("Sara").startswith("rejected")


def test_import_rejects_tom_because_he_joined_after_the_run_date() -> None:
    assert import_line_for("Tom").startswith("rejected")


def test_import_accepts_ines() -> None:
    assert import_line_for("Ines").startswith("accepted")


def test_import_rejects_omar() -> None:
    assert import_line_for("Omar").startswith("rejected")


def test_import_rejects_lena() -> None:
    assert import_line_for("Lena").startswith("rejected")


def test_import_rejects_kofi() -> None:
    assert import_line_for("Kofi").startswith("rejected")


def test_import_rejects_hana() -> None:
    assert import_line_for("Hana").startswith("rejected")


def test_import_rejected_lines_give_a_reason() -> None:
    for name in ("Omar", "Lena", "Kofi", "Hana", "Sara", "Tom"):
        _, _, reason = import_line_for(name).partition(" - ")
        assert reason.strip(), f"{name} was rejected with no reason"


HEADER = "first_name,last_name,email,group,joined_on,consent"


def test_read_signups_gives_2_good_subscribers_and_6_problems() -> None:
    result = read_signups(Path(NEW_SIGNUPS), date(2026, 11, 20))
    assert len(result.good) == 2
    assert len(result.problems) == 6


def test_read_signups_problems_name_their_row_and_field() -> None:
    # Row 1 is the header line, so Maria is row 2 and Omar is row 3.
    result = read_signups(Path(NEW_SIGNUPS), date(2026, 11, 20))
    assert [(p.row, p.field) for p in result.problems] == [
        (3, "email"),  # Omar: no email
        (4, "consent"),  # Lena: no consent
        (5, "group"),  # Kofi: "Gift Buyers"
        (6, "joined_on"),  # Hana: 21/10/2026
        (7, "email"),  # Sara: not @example.com
        (8, "joined_on"),  # Tom: after the run date
    ]


def test_read_subscribers_reports_every_bad_row_instead_of_raising(tmp_path: Path) -> None:
    bad = tmp_path / "subs.csv"
    bad.write_text(
        f"{HEADER}\n"
        "Ayesha,Khan,ayesha.khan@example.com,tea-curious,2026-09-14,waitlist form\n"
        "Bob,Ray,not-an-email,tea-curious,2026-09-14,waitlist form\n"
        "Cy,Lo,cy.lo@example.com,nope,2026-09-14,\n"
    )
    result = read_subscribers(bad)
    assert len(result.good) == 1
    assert [(p.row, p.field) for p in result.problems] == [
        (3, "email"),
        (4, "group"),
        (4, "consent"),
    ]


def test_import_prints_every_problem_with_its_row_and_exits_1() -> None:
    result = run_raw("import", NEW_SIGNUPS, "--run-date", RUN_DATE)
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    rejected = [l for l in result.stdout.splitlines() if l.startswith("rejected")]
    assert len(rejected) == 6
    assert "row 3" in import_line_for("Omar")
    assert "email" in import_line_for("Omar")


def test_import_with_no_file_says_so_in_one_sentence_and_exits_2() -> None:
    result = run_raw("import", "data/nope.csv", "--run-date", RUN_DATE)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "data/nope.csv" in result.stderr


def test_import_with_wrong_columns_says_so_in_one_sentence_and_exits_2(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong.csv"
    wrong.write_text("name,mail\nMaria,maria@example.com\n")
    result = run_raw("import", str(wrong), "--run-date", RUN_DATE)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "Traceback" not in result.stderr
    assert "first_name" in result.stderr
