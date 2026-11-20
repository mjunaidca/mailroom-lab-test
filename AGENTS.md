# Mailroom

Mailroom is a command-line tool for one newsletter: Kettlebird Tea's Steep Club. It reads the subscribers, checks an issue, and sends it to a practice mail server.

## Rules

- Use uv for everything (project setup, dependencies, running code, tests).
- Never use a real person's email address. Use @example.com, and @resend.dev for practice sends.
- Commit and push after every step.
- Every change goes on a branch and arrives as a pull request. Never commit to main; never merge a pull request unless asked.
- Behaviors first. The user gives the expected answers; you write them as checks in checks.py, show them failing, then write the code.
- Never read today's date inside the logic. Pass the run date in. Only the command line may read today's date.
- When something breaks, show me the full error exactly as printed before changing anything.
- Length means Python's `len()`, i.e. code points, not what a reader sees. "👍🏽 Thanks for joining" is 21 (👍🏽 counts as 2), not 20. Don't add a grapheme-counting library.
- I decide the test cases and their answers. Never change an expected answer to make a test pass.
- One module per job. Only the commands module prints.
- Every function has type hints, and pyright must be clean (`uv run pyright` reports 0 errors).
- Pass Subscriber and Issue objects around, never raw rows or raw text.
- Data from outside goes through the model before any code uses it.
- Report every problem with its row, never just the first. No traceback for a user's mistake: bad rows exit 1 with the full report; a missing file or wrong columns stop with one plain sentence and exit 2.
- The server's address and the key come from the environment (`RESEND_API_URL`, default `http://localhost:4000`; `RESEND_API_KEY`, default `re_practice`), never written into code. Sending works only against localhost.
- Handle each server status on purpose: a 422 shows the server's own message, a 404 says the id is unknown, no connection says the practice server is not running and how to start it (`npx emulate@0.12.3 start --service resend`). Never retry a 4xx (a 429 is the one exception, below).
- Send with a limit on how many at once: `send --at-once N` uses asyncio and never has more than N requests in flight (N is a whole number of at least 1). Results come back in the plan's order, however the requests finish. `--latency` is awaited before each request inside the limit, so the waits overlap. The localhost and practice-address guards check the whole plan before the first request goes out.
- Retry only what can succeed later: no connection, a timeout, a 429 or a 5xx. At most 3 tries in all, with growing waits (0.5 s, then 1 s). Never retry any other 4xx; it is the server's final answer. Anything else that goes wrong is not retried either.
- Every send has an idempotency key, made from the issue and the recipient, and every try of one email carries the same key. That is what makes a retry safe: the server sends one email per key, and the same key with a different email gets a 409.
