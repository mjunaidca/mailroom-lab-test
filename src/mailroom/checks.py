from mailroom.issue import LINK_PATTERN, MAX_PREVIEW_LENGTH, MAX_SUBJECT_LENGTH


def check_subject(issue_text):
    """Return a list of problems with the issue's Subject line; empty if fine."""
    for line in issue_text.splitlines():
        if line.startswith("Subject:"):
            subject = line[len("Subject:"):].strip()
            if not subject:
                return ["empty"]
            if len(subject) > MAX_SUBJECT_LENGTH:
                return ["too long"]
            return []
    return ["missing"]


def check_issue(issue_text):
    """Return a list of every problem in the issue; empty if fine."""
    problems = [f"subject: {p}" for p in check_subject(issue_text)]
    lines = issue_text.splitlines()

    for line in lines:
        if line.startswith("Preview:"):
            if len(line[len("Preview:"):].strip()) > MAX_PREVIEW_LENGTH:
                problems.append("preview: too long")
            break

    if "{{first_name}}" not in issue_text:
        problems.append("greeting: missing {{first_name}}")

    links = LINK_PATTERN.findall(issue_text)
    if len(links) != 1:
        problems.append(f"link: expected exactly 1, found {len(links)}")

    has_reason = any(line.startswith("You're getting this because") for line in lines)
    has_unsubscribe = any("Unsubscribe: {{unsubscribe_url}}" in line for line in lines)
    if not (has_reason and has_unsubscribe):
        problems.append("footer: missing or incomplete")

    return problems
