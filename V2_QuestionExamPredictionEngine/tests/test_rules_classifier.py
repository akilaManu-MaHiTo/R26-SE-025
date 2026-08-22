from app.classifier.rules import classify_by_rules


def test_sql_query_classifies_as_sql_coding_apply():
    result = classify_by_rules("Write a SQL SELECT query that joins two tables.")
    assert result.topic_assignments[0].topic == "SQL"
    assert result.bloom_level == "Apply"
    assert result.question_type == "coding"


def test_attribute_closure_classifies_schema_refinement():
    result = classify_by_rules("Find the primary key using attribute closure.")
    assert result.topic_assignments[0].topic == "Schema Refinement"
    assert result.bloom_level == "Apply"


def test_topic_weights_sum_to_one():
    result = classify_by_rules("Explain entity relationships and write a SQL query.")
    total = sum(a.weight for a in result.topic_assignments)
    assert abs(total - 1.0) < 1e-6


def test_unknown_text_is_low_confidence():
    result = classify_by_rules("Discuss the history of computing.")
    assert result.confidence == "low"
    assert result.bloom_level == "Understand"