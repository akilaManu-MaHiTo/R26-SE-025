import unittest

from src.agents.v2.normalize import (
    normalize_assessment,
    normalize_course,
    normalize_question,
    normalize_question_no,
)


class NormalizeQuestionNumberTests(unittest.TestCase):
    def test_numeric_forms_join_to_same_key(self):
        self.assertEqual(normalize_question_no("01"), "1")
        self.assertEqual(normalize_question_no("1"), "1")
        self.assertEqual(normalize_question_no(1), "1")
        self.assertEqual(normalize_question_no("Q1"), "Q1")
        self.assertEqual(normalize_question_no(None), "")


class NormalizeCourseTests(unittest.TestCase):
    def test_from_sample_document(self):
        course = normalize_course(
            {
                "_id": "ObjectId('64b8f1a2c39d2a1b5e000001')",
                "code": " se3040 ",
                "name": "Software Architecture",
                "description": "Advanced architecture",
            }
        )
        self.assertEqual(course.course_id, "64b8f1a2c39d2a1b5e000001")
        self.assertEqual(course.subject_code, "SE3040")
        self.assertEqual(course.name, "Software Architecture")


class NormalizeAssessmentTests(unittest.TestCase):
    SAMPLE = {
        "_id": "ObjectId('64b8f1a2c39d2a1b5e000002')",
        "session_name": "Semester 1 Final Exam",
        "subject_code": "SE3040",
        "filename": "rubric.pdf",
        "parsed_at": 1720000000.123,
    }

    def test_uses_rubric_id_as_assessment_id(self):
        assessment = normalize_assessment(self.SAMPLE)
        self.assertEqual(assessment.assessment_id, "64b8f1a2c39d2a1b5e000002")
        self.assertEqual(assessment.rubric_id, "64b8f1a2c39d2a1b5e000002")
        self.assertEqual(assessment.subject_code, "SE3040")
        self.assertEqual(assessment.rubric_filename, "rubric.pdf")
        self.assertIsNotNone(assessment.parsed_at)

    def test_slug_fallback_when_id_missing(self):
        doc = dict(self.SAMPLE)
        doc.pop("_id")
        assessment = normalize_assessment(doc)
        self.assertEqual(assessment.assessment_id, "SE3040:semester-1-final-exam")


class NormalizeQuestionTests(unittest.TestCase):
    def setUp(self):
        self.assessment = normalize_assessment(
            {
                "_id": "ObjectId('64b8f1a2c39d2a1b5e000002')",
                "session_name": "Semester 1 Final Exam",
                "subject_code": "SE3040",
            }
        )

    def test_from_sample_document(self):
        question = normalize_question(
            {
                "question_no": "01",
                "question_text": "Explain two-phase locking.",
                "max_marks": 5,
                "criteria": [
                    {"point": "Mentions growing phase", "marks": 2},
                    {"point": "Mentions shrinking phase", "marks": 2},
                    {"point": "Defines lock point", "marks": 1},
                ],
                "model_answer": "A lock point is ...",
            },
            self.assessment,
        )
        self.assertEqual(question.question_no_normalized, "1")
        self.assertEqual(question.question_no_raw, "01")
        self.assertEqual(question.max_marks, 5)
        self.assertEqual(len(question.rubric_criteria), 3)
        self.assertEqual(question.rubric_criteria[0].point, "Mentions growing phase")
        self.assertEqual(question.model_answer, "A lock point is ...")
        self.assertEqual(
            question.question_id,
            "64b8f1a2c39d2a1b5e000002:1",
        )

    def test_integer_question_no(self):
        question = normalize_question(
            {"question_no": 2, "question_text": "Define a primary key.", "max_marks": 5},
            self.assessment,
        )
        self.assertEqual(question.question_no_normalized, "2")


if __name__ == "__main__":
    unittest.main()
