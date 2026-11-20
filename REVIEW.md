# Reviewing a Mailroom change

Source: `AGENTS.md`. Part 1 is what only a reviewer can catch: no test, pyright or CI step will fail if these are broken. Part 2 is what the tools enforce, so the reviewer only confirms they actually ran.

## Part 1: Rules no test can catch

### Process and evidence

- [ ] **Branch and PR.** The change is on a branch and arrives as a pull request. Nothing was committed to `main`. Nobody merged a PR that the user did not ask to merge.
- [ ] **Evidence is real.** The PR template is filled in. Under Evidence, the output of `uv run pytest`, `uv run pyright` and `uv run mailroom check issues/issue-01.md` is pasted in full. Look for summaries, trimmed lines, and output that reads as if it was written from memory.
- [ ] **Behaviors first.** The commit history shows the checks in `checks.py` added and failing before the code that makes them pass. The user supplied the expected answers.
- [ ] **No expected answer was changed to make a test pass.** Read the diff of `checks.py` for edited expected values. Any such edit needs the user's decision on record.
- [ ] **Commit and push after every step.** The history is stepwise, not one large commit.
- [ ] **Failures were shown first.** When something broke, the full error was shown exactly as printed before any fix.
- [ ] **Skipped steps are said so.** If a step was skipped, or a check fails, the PR says so plainly.

### Design rules a grep or a green run would miss

- [ ] **Today's date is never read inside the logic.** The run date is a parameter. Only the command line reads the clock.
- [ ] **One module per job. Only the commands module prints.** No `print` and no direct writes to stdout or stderr elsewhere.
- [ ] **Subscriber and Issue objects are passed around, never raw rows or raw text.** Check function signatures for `dict`, `str` or `list[str]` standing in for a model.
- [ ] **Data from outside goes through the model before any code uses it.** CSV rows, issue files, and server responses are parsed into models at the edge.
- [ ] **Length is `len()`, in code points.** No grapheme-counting library was added, and no dependency was added to get around the rule. Example: "👍🏽 Thanks for joining" is 21.
- [ ] **The server address and key come from the environment.** `RESEND_API_URL` (default `http://localhost:4000`) and `RESEND_API_KEY` (default `re_practice`) are not written into code or fixtures.
- [ ] **No real person's email address anywhere,** including fixtures, docs, and the PR text. Only `@example.com`, or `@resend.dev` for practice sends.
- [ ] **uv for everything.** No `pip`, `python -m`, or a bare `pytest` in docs, scripts, or the PR.
- [ ] **No pull request was merged and no branch protection was bypassed** to get the change in.

### Behavior a test could cover but probably does not, so read it

- [ ] **User mistakes give no traceback.** Bad rows exit 1 with the full report, every problem with its row and not just the first. A missing file or wrong columns stops with one plain sentence and exits 2.
- [ ] **Each server status is handled on purpose.** 422 shows the server's own message. 404 says the id is unknown. No connection says the practice server is not running and gives `npx emulate@0.12.3 start --service resend`.
- [ ] **No retry of a 4xx** except 429. Nothing outside the retry list is retried.
- [ ] **Guards run on the whole plan before the first request.** Both the localhost guard and the practice-address guard.

## Part 2: Rules the tools enforce, so confirm they ran

- [ ] `uv run pyright` reports 0 errors, and every function has type hints.
- [ ] `uv run pytest` passes.
- [ ] `uv run mailroom check` passes on every issue, as CI runs it.
- [ ] The CI `checks` check is green. `main` requires it and a pull request.
- [ ] `send --at-once N`: asyncio, never more than N requests in flight, N a whole number of at least 1. Results come back in the plan's order. `--latency` is awaited before each request inside the limit, so the waits overlap.
- [ ] Retry: at most 3 tries in all, waits of 0.5 s then 1 s. Retried only on no connection, a timeout, a 429 or a 5xx.
- [ ] Idempotency: every send has a key made from the issue and the recipient. Every try of one email carries the same key. The same key with a different email gets a 409.

## Review order

1. Part 1, process and evidence, before reading any code.
2. Part 1, design rules, then behavior, against the diff.
3. Part 2, by looking at the pasted evidence and the CI run.
