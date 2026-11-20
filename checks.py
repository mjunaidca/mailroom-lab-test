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

print("All checks passed.")
