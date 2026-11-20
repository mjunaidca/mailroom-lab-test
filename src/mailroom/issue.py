import re

MAX_SUBJECT_LENGTH = 50
MAX_PREVIEW_LENGTH = 90
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(https?://[^)\s]+\)")
