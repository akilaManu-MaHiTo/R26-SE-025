# Lecturer question-paper preview

Open an exam in the lecturer analytics dashboard and select **View question paper** in the header. This read-only preview loads saved essay question wording and marking criteria plus the explicitly linked diagram marking rubric. It does not return student answers or run grading/analytics inference.

`GET /api/lecturers/exams/{course_code}/{session_name}/paper?year=2025&month=4&semester=1` resolves a unique canonical `examkeys` record. Matching accepts the same explicit numeric/string and Final/Final Examination representations as reconstruction. Conflicting keys or metadata are excluded; duplicate canonical identities are rejected. Essay definitions come from the existing rubric collection. Diagram rubrics require exact saved `guideline_object_id` references; an unrelated rubric is never inferred from its existence.

The preview flags missing definitions, duplicate questions, ambiguous diagram rubrics and invalid maxima. Unknown marks remain null. Nonfinite source numbers become null for JSON serialization. Only selected question/rubric fields are returned; rosters, submissions and evaluations are excluded from the response.

Read-only verification against gradev5 on 2026-10-16 returned five essays, one diagram rubric, 11 diagram criteria and 55 maximum marks. The original diagram question wording and recorded question number are missing, so the preview explicitly remains incomplete. Essay wording is the saved extraction and may consist of headings rather than the original full prompt.

Tests cover matching, cross-exam exclusion, canonical ambiguity, duplicate definitions, missing rubrics, invalid marks, response privacy, loading errors/retry and stale responses after switching exams. No database changes or new collections are required.
