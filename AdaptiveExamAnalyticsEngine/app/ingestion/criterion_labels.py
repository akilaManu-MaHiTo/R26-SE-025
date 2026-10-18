"""Shared conservative matching for saved essay criterion labels."""


def criterion_label_key(value):
    if not isinstance(value, str):
        return None
    label = value.strip().casefold()
    # Saved rubric extraction can append a stray ')'; preserve balanced/internal punctuation.
    depth, unmatched = 0, set()
    for index, char in enumerate(label):
        if char == "(":
            depth += 1
        elif char == ")":
            if depth:
                depth -= 1
            else:
                unmatched.add(index)
    while label and len(label) - 1 in unmatched:
        label = label[:-1].rstrip()
    return label
