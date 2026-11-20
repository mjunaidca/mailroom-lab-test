import subprocess

result = subprocess.run(
    ["uv", "run", "mailroom.py", "subscribers"],
    capture_output=True,
    text=True,
)
lines = result.stdout.splitlines()

assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
assert "Total: 24" in lines, f"expected 'Total: 24', got {lines}"
assert "tea-curious: 8" in lines, f"expected 'tea-curious: 8', got {lines}"
assert "gift-buyers: 8" in lines, f"expected 'gift-buyers: 8', got {lines}"
assert "daily-drinkers: 8" in lines, f"expected 'daily-drinkers: 8', got {lines}"



def run(*args):
    return subprocess.run(
        ["uv", "run", "mailroom.py", *args], capture_output=True, text=True
    )


result = run("subscribers", "--since-days", "30", "--run-date", "2026-11-20")
lines = result.stdout.splitlines()
assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
assert "Joined in last 30 days: 7" in lines, f"expected 'Joined in last 30 days: 7', got {lines}"

result = run("next-send", "--run-date", "2026-11-20")
assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
assert result.stdout.splitlines() == ["Next send: 2026-12-07"], f"got {result.stdout!r}"

result = run("next-send", "--run-date", "2026-12-07")
assert result.returncode == 0, f"mailroom.py failed: {result.stderr.strip()}"
assert result.stdout.splitlines() == ["Next send: 2027-01-04"], f"got {result.stdout!r}"

print("All checks passed.")
