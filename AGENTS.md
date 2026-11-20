# Mailroom

Mailroom is a command-line tool for one newsletter: Kettlebird Tea's Steep Club. It reads the subscribers, checks an issue, and sends it to a practice mail server.

## Rules

- Use uv for everything (project setup, dependencies, running code, tests).
- Never use a real person's email address. Use @example.com, and @resend.dev for practice sends.
- Commit and push after every step.
- Behaviors first. The user gives the expected answers; you write them as checks in checks.py, show them failing, then write the code.
- Never read today's date inside the logic. Pass the run date in. Only the command line may read today's date.
- When something breaks, show me the full error exactly as printed before changing anything.
- Length means Python's `len()`, i.e. code points, not what a reader sees. "👍🏽 Thanks for joining" is 21 (👍🏽 counts as 2), not 20. Don't add a grapheme-counting library.
- I decide the test cases and their answers. Never change an expected answer to make a test pass.
- One module per job. Only the commands module prints.
