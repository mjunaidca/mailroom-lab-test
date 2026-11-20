# Mailroom

Mailroom is a command-line tool for one newsletter: Kettlebird Tea's Steep Club. It reads the subscribers, checks an issue, and sends it to a practice mail server.

## Rules

- Use uv for everything (project setup, dependencies, running code, tests).
- Never use a real person's email address. Use @example.com, and @resend.dev for practice sends.
- Commit and push after every step.
- Behaviors first. The user gives the expected answers; you write them as checks in checks.py, show them failing, then write the code.
- Never read today's date inside the logic. Pass the run date in. Only the command line may read today's date.
- When something breaks, show me the full error exactly as printed before changing anything.
- I decide the test cases and their answers. Never change an expected answer to make a test pass.
