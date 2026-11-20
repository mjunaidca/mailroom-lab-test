import asyncio
import json
import os
import re
import time
import subprocess
from datetime import date
from pathlib import Path

import httpx
import pytest

from mailroom import commands, resend, sending
from mailroom.checks import check_issue, check_subject
from mailroom.issue import Issue
from mailroom.plan import Entry, Plan, build_plan
from mailroom.problems import InputError
from mailroom.signups import read_signups
from mailroom.subscribers import joined_since, read_subscribers


def run_raw(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "mailroom", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
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


PLAN = Path(__file__).parent / "outbox" / "plan.json"
SEND_DATE = "2026-12-07"


def test_send_dry_run_writes_a_plan_of_24_entries_with_the_run_date() -> None:
    PLAN.unlink(missing_ok=True)
    run("send", "issues/issue-01.md", "--dry-run", "--run-date", SEND_DATE)
    plan = json.loads(PLAN.read_text())
    assert plan["run_date"] == SEND_DATE
    assert len(plan["entries"]) == 24


def test_send_dry_run_first_entry_is_to_ayesha_and_says_hi_ayesha() -> None:
    PLAN.unlink(missing_ok=True)
    run("send", "issues/issue-01.md", "--dry-run", "--run-date", SEND_DATE)
    first = json.loads(PLAN.read_text())["entries"][0]
    assert first["to"] == "ayesha.khan@example.com"
    assert first["subject"] == "The Steep Club opens Monday"
    assert "Hi Ayesha" in first["text"]
    assert "{{first_name}}" not in first["text"]


def test_send_dry_run_with_an_issue_that_fails_the_check_writes_no_plan(tmp_path: Path) -> None:
    bad_issue = tmp_path / "bad-issue.md"
    bad_issue.write_text(issue_01_with("{{first_name}}", "there"))
    PLAN.unlink(missing_ok=True)
    result = run_raw("send", str(bad_issue), "--dry-run", "--run-date", SEND_DATE)
    assert result.returncode == 1
    assert "greeting: missing {{first_name}}" in result.stdout
    assert not PLAN.exists()


def test_send_with_no_issue_file_says_so_in_one_sentence_and_exits_2() -> None:
    result = run_raw("send", "issues/nope.md", "--dry-run", "--run-date", SEND_DATE)
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "issues/nope.md" in result.stderr


def test_outbox_is_kept_out_of_git() -> None:
    ignored = subprocess.run(["git", "check-ignore", "-q", "outbox/plan.json"])
    assert ignored.returncode == 0


# --- send-one: one email to the practice server (no test needs the server) ---

ISSUE_01 = Path(__file__).parent / "issues" / "issue-01.md"
PRACTICE = resend.Settings(url="http://localhost:4000", key="re_practice")


def fake_server(seen: list[httpx.Request], status: int = 200, body: dict[str, object] | None = None) -> httpx.Client:
    """A stand-in for the practice server. Records every request it gets."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if status != 200:
            return httpx.Response(status, json=body or {"message": "no"})
        if request.method == "POST":
            return httpx.Response(200, json={"id": "em_123"})
        return httpx.Response(200, json={"id": "em_123", "last_event": "delivered"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_settings_default_to_localhost_4000_and_re_practice() -> None:
    settings = resend.Settings.from_env({})
    assert settings.url == "http://localhost:4000"
    assert settings.key == "re_practice"


def test_settings_come_from_resend_api_url_and_resend_api_key() -> None:
    settings = resend.Settings.from_env({"RESEND_API_URL": "http://localhost:9999", "RESEND_API_KEY": "re_other"})
    assert settings.url == "http://localhost:9999"
    assert settings.key == "re_other"


def test_send_email_posts_to_emails_with_from_to_subject_text_and_a_bearer_key() -> None:
    seen: list[httpx.Request] = []
    resend.send_email(fake_server(seen), PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == "http://localhost:4000/emails"
    assert request.headers["Authorization"] == "Bearer re_practice"
    body = json.loads(request.content)
    assert body["from"] == "onboarding@resend.dev"
    assert body["to"] == ["delivered@resend.dev"]
    assert body["subject"] == "The Steep Club opens Monday"
    assert "{{first_name}}" not in body["text"]


def test_send_email_gives_back_the_status_code_and_the_id() -> None:
    sent = resend.send_email(fake_server([]), PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert sent == resend.Sent(status_code=200, id="em_123")


def test_get_status_gets_the_email_back_and_reads_its_last_event() -> None:
    seen: list[httpx.Request] = []
    status = resend.get_status(fake_server(seen), PRACTICE, "em_123")
    assert status == "delivered"
    assert seen[0].method == "GET"
    assert str(seen[0].url) == "http://localhost:4000/emails/em_123"
    assert seen[0].headers["Authorization"] == "Bearer re_practice"


@pytest.mark.parametrize(
    "url",
    [
        "https://api.resend.com",
        "http://localhost.evil.com:4000",
        "http://localhost@evil.com:4000",
        "http://evil.com/localhost",
    ],
)
def test_send_email_refuses_a_server_that_is_not_localhost_and_sends_nothing(url: str) -> None:
    seen: list[httpx.Request] = []
    settings = resend.Settings(url=url, key="re_practice")
    with pytest.raises(InputError):
        resend.send_email(fake_server(seen), settings, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert seen == []


def test_get_status_refuses_a_server_that_is_not_localhost_and_asks_nothing() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.get_status(fake_server(seen), resend.Settings(url="https://api.resend.com", key="k"), "em_123")
    assert seen == []


@pytest.mark.parametrize(
    "to",
    ["someone@gmail.com", "x@example.com.evil.com", "x@sub.example.com", "example.com", "a@b@example.com"],
)
def test_send_email_refuses_a_recipient_not_at_example_com_or_resend_dev_and_sends_nothing(to: str) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.send_email(fake_server(seen), PRACTICE, to, Issue.from_text(ISSUE_01.read_text()))
    assert seen == []


@pytest.mark.parametrize("to", ["delivered@resend.dev", "maria@example.com", "Maria@Example.COM"])
def test_send_email_accepts_a_recipient_at_example_com_or_resend_dev(to: str) -> None:
    seen: list[httpx.Request] = []
    resend.send_email(fake_server(seen), PRACTICE, to, Issue.from_text(ISSUE_01.read_text()))
    assert len(seen) == 1


def test_send_email_when_the_server_says_no_is_one_plain_sentence_with_the_code() -> None:
    with pytest.raises(InputError, match="401") as error:
        resend.send_email(fake_server([], status=401), PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert "\n" not in str(error.value)


def test_send_email_when_the_server_is_not_running_is_one_plain_sentence() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    with pytest.raises(InputError, match="localhost:4000") as error:
        resend.send_email(client, PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert "\n" not in str(error.value)


SERVER_422 = {"statusCode": 422, "name": "validation_error", "message": "Missing required field: subject"}
SERVER_404 = {"statusCode": 404, "name": "not_found", "message": "Email not found"}
START_COMMAND = "npx emulate@0.12.3 start --service resend"


def test_a_422_shows_the_servers_own_message_in_one_sentence() -> None:
    with pytest.raises(InputError, match="Missing required field: subject") as error:
        resend.send_email(fake_server([], status=422, body=SERVER_422), PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert "\n" not in str(error.value)


def test_a_422_is_sent_once_and_never_retried() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.send_email(fake_server(seen, status=422, body=SERVER_422), PRACTICE, "delivered@resend.dev", Issue.from_text(ISSUE_01.read_text()))
    assert len(seen) == 1


def test_a_404_on_an_email_id_says_the_id_is_unknown() -> None:
    with pytest.raises(InputError, match="em_nope") as error:
        resend.get_status(fake_server([], status=404, body=SERVER_404), PRACTICE, "em_nope")
    assert "unknown" in str(error.value)
    assert "\n" not in str(error.value)


@pytest.mark.parametrize("status", [400, 401, 404, 409, 422])
def test_no_4xx_is_ever_retried(status: int) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.get_status(fake_server(seen, status=status), PRACTICE, "em_123")
    assert len(seen) == 1


def test_no_connection_says_the_practice_server_is_not_running_and_how_to_start_it() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    with pytest.raises(InputError, match="not running") as error:
        resend.get_status(client, PRACTICE, "em_123")
    assert START_COMMAND in str(error.value)
    assert "\n" not in str(error.value)


def test_send_one_command_prints_the_status_code_and_the_id_then_the_status(capsys: pytest.CaptureFixture[str]) -> None:
    code = commands.send_one(ISSUE_01, "delivered@resend.dev", PRACTICE, fake_server([]))
    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["Sent: 200 em_123", "Status: delivered"]


def test_send_one_command_with_an_issue_that_fails_the_check_sends_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_issue = tmp_path / "bad-issue.md"
    bad_issue.write_text(issue_01_with("{{first_name}}", "there"))
    seen: list[httpx.Request] = []
    code = commands.send_one(bad_issue, "delivered@resend.dev", PRACTICE, fake_server(seen))
    assert code == 1
    assert "greeting: missing {{first_name}}" in capsys.readouterr().out
    assert seen == []


def test_send_one_from_the_command_line_refuses_a_server_that_is_not_localhost_with_one_sentence_and_exit_2() -> None:
    result = run_raw(
        "send-one", "issues/issue-01.md", "--to", "delivered@resend.dev",
        env={"RESEND_API_URL": "https://api.resend.com"},
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


def test_send_one_from_the_command_line_refuses_a_real_recipient_with_one_sentence_and_exit_2() -> None:
    result = run_raw("send-one", "issues/issue-01.md", "--to", "someone@gmail.com")
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1
    assert "someone@gmail.com" in result.stderr


# --- send: the whole plan, one by one, with a wait (latency) before each request ---


def plan_of(count: int) -> Plan:
    entries = [Entry(to=f"person{i}@example.com", subject="Hello", text=f"Hi {i}", key=f"key-{i}") for i in range(count)]
    return Plan(run_date=date(2026, 12, 7), entries=entries)


def recipient_of(request: httpx.Request) -> str:
    return json.loads(request.content)["to"][0]


def echo_server(seen: list[httpx.Request], times: list[float] | None = None) -> httpx.Client:
    """Answers each send with an id made from the recipient, so a result can be matched to its entry."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if times is not None:
            times.append(time.perf_counter())
        return httpx.Response(200, json={"id": f"em_{recipient_of(request)}"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_all_sends_every_entry_in_the_plans_order() -> None:
    seen: list[httpx.Request] = []
    sent = sending.send_all(plan_of(4), PRACTICE, echo_server(seen), 0)
    assert [recipient_of(r) for r in seen] == [f"person{i}@example.com" for i in range(4)]
    assert [s.id for s in sent] == [f"em_person{i}@example.com" for i in range(4)]


def test_send_all_waits_the_latency_before_each_request() -> None:
    times: list[float] = []
    start = time.perf_counter()
    sending.send_all(plan_of(4), PRACTICE, echo_server([], times), 0.05)
    assert times[0] - start >= 0.04
    assert all(later - earlier >= 0.04 for earlier, later in zip(times, times[1:]))


@pytest.mark.parametrize("url", ["https://api.resend.com", "http://example.com:4000"])
def test_send_all_refuses_a_server_that_is_not_localhost_and_sends_nothing(url: str) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="localhost"):
        sending.send_all(plan_of(3), resend.Settings(url=url, key="re_practice"), echo_server(seen), 0)
    assert seen == []


def test_send_all_with_a_real_address_anywhere_in_the_plan_sends_nothing() -> None:
    plan = plan_of(3)
    plan.entries[2] = Entry(to="someone@gmail.com", subject="Hello", text="Hi", key="key-x")
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="someone@gmail.com"):
        sending.send_all(plan, PRACTICE, echo_server(seen), 0)
    assert seen == []


def test_send_command_sends_all_24_and_prints_how_long_it_took(capsys: pytest.CaptureFixture[str]) -> None:
    seen: list[httpx.Request] = []
    transport = echo_server(seen)._transport  # the fake server's transport
    code = commands.send_now(ISSUE_01, date(2026, 12, 7), PRACTICE, 0, transport)
    assert code == 0
    assert len(seen) == 24
    assert re.fullmatch(r"Sent 24 emails in \d+\.\d{2} seconds", capsys.readouterr().out.strip())


def test_send_command_with_an_issue_that_fails_the_check_sends_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad_issue = tmp_path / "bad-issue.md"
    bad_issue.write_text(issue_01_with("{{first_name}}", "there"))
    seen: list[httpx.Request] = []
    code = commands.send_now(bad_issue, date(2026, 12, 7), PRACTICE, 0, echo_server(seen)._transport)
    assert code == 1
    assert "greeting: missing {{first_name}}" in capsys.readouterr().out
    assert seen == []


def test_send_from_the_command_line_refuses_a_server_that_is_not_localhost_with_one_sentence_and_exit_2() -> None:
    result = run_raw(
        "send", "issues/issue-01.md", "--run-date", SEND_DATE, "--latency", "0.3",
        env={"RESEND_API_URL": "https://api.resend.com"},
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


def test_send_with_a_negative_latency_is_refused_with_exit_2() -> None:
    result = run_raw("send", "issues/issue-01.md", "--run-date", SEND_DATE, "--latency=-1")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error: argument --latency: latency cannot be negative" in result.stderr


# --- send --at-once N: the same send with asyncio, at most N at a time, results in the plan's order ---


class Busy:
    """What a fake async server saw: how many requests were in flight at once, and the order they finished."""

    def __init__(self) -> None:
        self.running = 0
        self.most_at_once = 0
        self.finished: list[str] = []


def async_echo_server(busy: Busy, seen: list[httpx.Request], slowest_first: bool = False) -> httpx.AsyncClient:
    """Each request takes a moment. With slowest_first, early entries take longest, so they finish last."""

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        to = recipient_of(request)
        busy.running += 1
        busy.most_at_once = max(busy.most_at_once, busy.running)
        if slowest_first:
            match = re.search(r"\d+", to)
            assert match is not None
            await asyncio.sleep(0.01 * (20 - int(match.group())))
        else:
            await asyncio.sleep(0.02)
        busy.running -= 1
        busy.finished.append(to)
        return httpx.Response(200, json={"id": f"em_{to}"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def send_at_once(plan: Plan, client: httpx.AsyncClient, latency: float = 0, limit: int = 5) -> list[resend.Sent]:
    async def go() -> list[resend.Sent]:
        async with client:
            return await sending.send_all_at_once(plan, PRACTICE, client, latency, limit)

    return asyncio.run(go())


def test_at_once_gives_the_results_in_the_plans_order_even_when_the_requests_finish_in_another_order() -> None:
    busy = Busy()
    plan = plan_of(10)
    sent = send_at_once(plan, async_echo_server(busy, [], slowest_first=True))
    assert busy.finished != [e.to for e in plan.entries]  # the server really did finish them out of order
    assert [s.id for s in sent] == [f"em_{e.to}" for e in plan.entries]


def test_at_once_5_never_has_more_than_5_requests_running_at_once() -> None:
    busy = Busy()
    sent = send_at_once(plan_of(24), async_echo_server(busy, []), limit=5)
    assert len(sent) == 24
    assert busy.most_at_once <= 5


def test_at_once_5_does_run_5_at_the_same_time() -> None:
    busy = Busy()
    send_at_once(plan_of(24), async_echo_server(busy, []), limit=5)
    assert busy.most_at_once == 5


def test_at_once_2_never_has_more_than_2_requests_running_at_once() -> None:
    busy = Busy()
    send_at_once(plan_of(10), async_echo_server(busy, []), limit=2)
    assert busy.most_at_once == 2


def test_at_once_waits_the_latency_before_each_request_but_the_waits_overlap() -> None:
    start = time.perf_counter()
    send_at_once(plan_of(10), async_echo_server(Busy(), []), latency=0.1, limit=5)
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.2  # 10 requests, 5 at a time: two rounds, each waiting 0.1 first
    assert elapsed < 0.8  # one by one it would be at least 10 * 0.1 = 1.0


def test_at_once_with_a_real_address_anywhere_in_the_plan_sends_nothing() -> None:
    plan = plan_of(8)
    plan.entries[7] = Entry(to="someone@gmail.com", subject="Hello", text="Hi", key="key-x")
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="someone@gmail.com"):
        send_at_once(plan, async_echo_server(Busy(), seen))
    assert seen == []


def test_send_command_with_at_once_5_sends_all_24_and_prints_how_long_it_took(capsys: pytest.CaptureFixture[str]) -> None:
    busy = Busy()
    seen: list[httpx.Request] = []
    transport = async_echo_server(busy, seen)._transport  # the fake server's transport
    code = commands.send_now(ISSUE_01, date(2026, 12, 7), PRACTICE, 0, at_once=5, async_transport=transport)
    assert code == 0
    assert len(seen) == 24
    assert busy.most_at_once <= 5
    assert re.fullmatch(r"Sent 24 emails in \d+\.\d{2} seconds", capsys.readouterr().out.strip())


@pytest.mark.parametrize("limit", ["0", "-3", "five"])
def test_at_once_must_be_a_whole_number_of_at_least_1_exit_2(limit: str) -> None:
    result = run_raw("send", "issues/issue-01.md", "--run-date", SEND_DATE, "--at-once", limit)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error: argument --at-once:" in result.stderr


def test_at_once_has_no_meaning_with_dry_run_exit_2() -> None:
    result = run_raw("send", "issues/issue-01.md", "--dry-run", "--run-date", SEND_DATE, "--at-once", "5")
    assert result.returncode == 2
    assert result.stdout == ""
    assert "--at-once" in result.stderr


def test_send_at_once_from_the_command_line_refuses_a_server_that_is_not_localhost_with_one_sentence_and_exit_2() -> None:
    result = run_raw(
        "send", "issues/issue-01.md", "--run-date", SEND_DATE, "--at-once", "5",
        env={"RESEND_API_URL": "https://api.resend.com"},
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert len(result.stderr.strip().splitlines()) == 1


# --- retry (only what can succeed later) and idempotency keys (so a retry cannot send twice) ---


@pytest.fixture(autouse=True)
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """No test really waits between tries. Every wait that was asked for is recorded here, in order."""
    asked: list[float] = []

    async def pause_async(seconds: float) -> None:
        asked.append(seconds)

    monkeypatch.setattr(resend, "pause", asked.append, raising=False)
    monkeypatch.setattr(resend, "pause_async", pause_async, raising=False)
    return asked


Outcome = int | type[httpx.TransportError]


def answer(outcome: Outcome | None, request: httpx.Request) -> httpx.Response:
    if outcome is None:
        return httpx.Response(200, json={"id": "em_123"})
    if isinstance(outcome, int):
        return httpx.Response(outcome, json={"message": "no"})
    raise outcome("scripted", request=request)


def scripted(seen: list[httpx.Request], *outcomes: Outcome) -> httpx.Client:
    """Answers the first request with the first outcome, the second with the second, and so on; then 200."""
    remaining = list(outcomes)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer(remaining.pop(0) if remaining else None, request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def scripted_async(seen: list[httpx.Request], *outcomes: Outcome) -> httpx.AsyncClient:
    remaining = list(outcomes)

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer(remaining.pop(0) if remaining else None, request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


ENTRY = Entry(to="delivered@resend.dev", subject="Hello", text="Hi", key="key-1")
ISSUE = Issue.from_text(ISSUE_01.read_text())

RETRYABLE: list[Outcome] = [429, 500, 502, 503, httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout]


@pytest.mark.parametrize("outcome", RETRYABLE)
def test_a_failure_that_can_succeed_later_is_tried_again_after_a_wait_and_then_succeeds(
    outcome: Outcome, waits: list[float]
) -> None:
    seen: list[httpx.Request] = []
    sent = resend.send_entry(scripted(seen, outcome), PRACTICE, ENTRY)
    assert sent.id == "em_123"
    assert len(seen) == 2
    assert len(waits) == 1
    assert waits[0] > 0


def test_it_gives_up_after_3_tries_in_all_with_growing_waits_and_the_last_5xx_sentence(waits: list[float]) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="503") as error:
        resend.send_entry(scripted(seen, 503, 503, 503, 503), PRACTICE, ENTRY)
    assert len(seen) == 3
    assert len(waits) == 2
    assert 0 < waits[0] < waits[1]
    assert "\n" not in str(error.value)


def test_a_429_that_keeps_coming_gives_up_after_3_tries(waits: list[float]) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="429"):
        resend.send_entry(scripted(seen, 429, 429, 429, 429), PRACTICE, ENTRY)
    assert len(seen) == 3


def test_no_connection_3_times_still_says_the_server_is_not_running_and_how_to_start_it() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="not running") as error:
        resend.send_entry(scripted(seen, *[httpx.ConnectError] * 4), PRACTICE, ENTRY)
    assert len(seen) == 3
    assert START_COMMAND in str(error.value)


def test_a_timeout_3_times_says_the_server_did_not_answer_in_time_not_that_it_is_not_running() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError, match="did not answer in time") as error:
        resend.send_entry(scripted(seen, *[httpx.ReadTimeout] * 4), PRACTICE, ENTRY)
    assert len(seen) == 3
    assert "not running" not in str(error.value)


@pytest.mark.parametrize("status", [400, 401, 404, 409, 422])
def test_a_send_that_gets_a_4xx_is_sent_once_and_never_retried(status: int, waits: list[float]) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.send_entry(scripted(seen, status), PRACTICE, ENTRY)
    assert len(seen) == 1
    assert waits == []


def test_a_failure_that_is_neither_no_connection_nor_a_timeout_is_not_retried() -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(InputError):
        resend.send_entry(scripted(seen, httpx.ReadError), PRACTICE, ENTRY)
    assert len(seen) == 1


def test_a_first_try_that_works_never_waits(waits: list[float]) -> None:
    seen: list[httpx.Request] = []
    resend.send_entry(scripted(seen), PRACTICE, ENTRY)
    assert len(seen) == 1
    assert waits == []


def test_asking_the_status_of_an_email_is_retried_the_same_way() -> None:
    seen: list[httpx.Request] = []
    client = scripted(seen, 503)
    with pytest.raises(InputError):  # the scripted 200 answer has no last_event, which is a different problem
        resend.get_status(client, PRACTICE, "em_123")
    assert len(seen) == 2


def test_the_async_send_retries_the_same_way(waits: list[float]) -> None:
    seen: list[httpx.Request] = []

    async def go() -> resend.Sent:
        async with scripted_async(seen, 503, httpx.ConnectError) as client:
            return await resend.send_entry_async(client, PRACTICE, ENTRY)

    assert asyncio.run(go()).id == "em_123"
    assert len(seen) == 3
    assert 0 < waits[0] < waits[1]


def test_the_async_send_never_retries_a_4xx(waits: list[float]) -> None:
    seen: list[httpx.Request] = []

    async def go() -> resend.Sent:
        async with scripted_async(seen, 409) as client:
            return await resend.send_entry_async(client, PRACTICE, ENTRY)

    with pytest.raises(InputError):
        asyncio.run(go())
    assert len(seen) == 1
    assert waits == []


def key_of(request: httpx.Request) -> str | None:
    return request.headers.get("Idempotency-Key")


def test_send_entry_sends_the_entrys_key_as_the_idempotency_key() -> None:
    seen: list[httpx.Request] = []
    resend.send_entry(scripted(seen), PRACTICE, ENTRY)
    assert key_of(seen[0]) == "key-1"


def test_send_email_sends_an_idempotency_key() -> None:
    seen: list[httpx.Request] = []
    resend.send_email(scripted(seen), PRACTICE, "delivered@resend.dev", ISSUE)
    assert key_of(seen[0])


def test_the_async_send_sends_the_entrys_key_as_the_idempotency_key() -> None:
    seen: list[httpx.Request] = []

    async def go() -> resend.Sent:
        async with scripted_async(seen) as client:
            return await resend.send_entry_async(client, PRACTICE, ENTRY)

    asyncio.run(go())
    assert key_of(seen[0]) == "key-1"


def test_every_try_of_one_email_carries_the_same_key() -> None:
    seen: list[httpx.Request] = []
    resend.send_entry(scripted(seen, 503, httpx.ReadTimeout), PRACTICE, ENTRY)
    assert [key_of(r) for r in seen] == ["key-1", "key-1", "key-1"]


def test_asking_for_a_status_sends_no_idempotency_key() -> None:
    seen: list[httpx.Request] = []
    resend.get_status(fake_server(seen), PRACTICE, "em_123")
    assert key_of(seen[0]) is None


SUBSCRIBERS_24 = read_subscribers().good


def plan_for(issue: Issue) -> Plan:
    return build_plan(issue, SUBSCRIBERS_24, date(2026, 12, 7))


def test_the_plan_gives_every_email_its_own_key() -> None:
    keys = [e.key for e in plan_for(ISSUE).entries]
    assert len(keys) == 24
    assert len(set(keys)) == 24
    assert all(keys)


def test_the_same_issue_and_recipient_make_the_same_key_on_another_day() -> None:
    later = build_plan(ISSUE, SUBSCRIBERS_24, date(2027, 1, 1))
    assert [e.key for e in later.entries] == [e.key for e in plan_for(ISSUE).entries]


def test_another_issue_makes_another_key_for_the_same_recipient() -> None:
    other = Issue(subject="A different issue", preview=ISSUE.preview, body=ISSUE.body)
    assert not set(e.key for e in plan_for(other).entries) & set(e.key for e in plan_for(ISSUE).entries)


def test_the_key_is_at_most_256_characters_and_does_not_contain_the_address() -> None:
    for entry in plan_for(ISSUE).entries:
        assert 0 < len(entry.key) <= 256
        assert "@" not in entry.key


# --- report: the send writes outbox/sent.json; report says how many each group got, and any failures ---


def send_all_24(sent_path: Path) -> None:
    transport = echo_server([])._transport
    assert commands.send_now(ISSUE_01, date(2026, 12, 7), PRACTICE, 0, transport, sent_path=sent_path) == 0


def test_send_writes_sent_json_with_each_emails_id_recipient_and_status(tmp_path: Path) -> None:
    sent_path = tmp_path / "sent.json"
    send_all_24(sent_path)
    records = json.loads(sent_path.read_text())
    assert len(records) == 24
    assert set(records[0]) == {"id", "to", "status"}
    assert records[0]["id"] == f"em_{records[0]['to']}"
    assert {r["status"] for r in records} == {"sent"}
    assert [r["to"] for r in records] == [s.email for s in read_subscribers().good]


def test_report_after_a_send_to_all_24_says_8_per_group_and_no_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sent_path = tmp_path / "sent.json"
    send_all_24(sent_path)
    capsys.readouterr()
    assert commands.report(sent_path) == 0
    assert capsys.readouterr().out.splitlines() == [
        "tea-curious: 8",
        "gift-buyers: 8",
        "daily-drinkers: 8",
        "Failures: none",
    ]


def test_report_lists_every_failure_with_its_recipient(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    people = read_subscribers().good
    sent_path = tmp_path / "sent.json"
    sent_path.write_text(json.dumps([
        {"id": f"em_{p.email}", "to": p.email, "status": "failed" if i in (0, 9) else "sent"}
        for i, p in enumerate(people)
    ]))
    assert commands.report(sent_path) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "Failures: 2" in lines
    assert sum(f"failed: {people[i].email}" in line for line in lines for i in (0, 9)) == 2


def test_report_counts_only_the_emails_that_went_out(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    people = read_subscribers().good
    sent_path = tmp_path / "sent.json"
    sent_path.write_text(json.dumps([
        {"id": f"em_{p.email}", "to": p.email, "status": "failed" if i == 0 else "sent"}
        for i, p in enumerate(people)
    ]))
    commands.report(sent_path)
    assert f"{people[0].group}: 7" in capsys.readouterr().out.splitlines()


def test_report_without_a_sent_json_is_one_plain_sentence(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="sent.json"):
        commands.report(tmp_path / "sent.json")



def test_report_from_the_command_line_never_shows_a_traceback() -> None:
    result = run_raw("report")
    assert "Traceback" not in result.stderr
    assert result.returncode in (0, 2)
