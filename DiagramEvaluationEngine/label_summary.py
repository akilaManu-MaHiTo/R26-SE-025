from collections import defaultdict


def print_label_summary(rows):
    target_labels = [
        "Attributes",
        "Entities",
        "Primary Key",
        "Relationships",
        "Weak Entity",
    ]
    normalized_target = {
        label.lower().replace("_", " "): label for label in target_labels
    }

    counts = {label: 0 for label in target_labels}
    ocr_names = defaultdict(list)

    for row in rows:
        raw_label = str(row.get("label", "")).strip()
        canonical_label = normalized_target.get(raw_label.lower().replace("_", " "))
        if not canonical_label:
            continue

        counts[canonical_label] += 1
        text = str(row.get("text", "")).strip()
        if text:
            ocr_names[canonical_label].append(text)

    print("\nDetected object summary:")
    for label in target_labels:
        names = ocr_names[label]
        print(f"- {label}: {counts[label]}")
        if names:
            print(f"  labeled names: {', '.join(names)}")
        else:
            print("  labeled names: (none)")
