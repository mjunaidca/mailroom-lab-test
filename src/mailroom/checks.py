from mailroom.issue import MAX_PREVIEW_LENGTH, MAX_SUBJECT_LENGTH, Issue


def check_subject(issue: Issue) -> list[str]:
    """Return a list of problems with the issue's Subject line; empty if fine."""
    if issue.subject is None:
        return ["missing"]
    if not issue.subject:
        return ["empty"]
    if len(issue.subject) > MAX_SUBJECT_LENGTH:
        return ["too long"]
    return []


def check_issue(issue: Issue) -> list[str]:
    """Return a list of every problem in the issue; empty if fine."""
    problems = [f"subject: {p}" for p in check_subject(issue)]

    if issue.preview is not None and len(issue.preview) > MAX_PREVIEW_LENGTH:
        problems.append("preview: too long")

    if issue.preview is not None and issue.preview == issue.subject:
        problems.append("preview: repeats the subject")

    if "{{first_name}}" not in issue.body:
        problems.append("greeting: missing {{first_name}}")

    if len(issue.links) != 1:
        problems.append(f"link: expected exactly 1, found {len(issue.links)}")

    for link in issue.links:
        if not link.startswith("https://"):
            problems.append(f"link: not https: {link}")

    lines = issue.body.splitlines()
    has_reason = any(line.startswith("You're getting this because") for line in lines)
    has_unsubscribe = any("Unsubscribe: {{unsubscribe_url}}" in line for line in lines)
    if not (has_reason and has_unsubscribe):
        problems.append("footer: missing or incomplete")

    return problems
