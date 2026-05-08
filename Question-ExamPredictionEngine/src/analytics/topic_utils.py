"""Helpers for resolving topic labels from exam data."""


def resolve_topic(exam_data, question_number, part_id=None, default="Unknown"):
    """Return the most specific topic available for a question part."""
    for question in exam_data.get("questions", []):
        if str(question.get("question_number")) != str(question_number):
            continue

        for part in question.get("parts", []):
            if part.get("part") != part_id:
                continue

            topic = part.get("topic")
            if topic:
                return topic
            break

        topic = question.get("topic")
        if topic:
            return topic

        if part_id is not None:
            return f"Q{question_number}{part_id}"

        return f"Q{question_number}"

    return default