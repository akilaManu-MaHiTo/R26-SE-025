"""End-to-end HTTP tests of the viva flow through the real FastAPI app + middleware.

Create viva -> analyze under it -> list / filter -> publish. Mongo is replaced by
small in-memory collections and the ML pipeline by a canned result; everything
else (session middleware, role checks, origin checks, routing, form parsing) is real.

  python -m unittest Gradex_AI_Server.app.tests.test_viva_flow_http -v
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi.testclient import TestClient

from Gradex_AI_Server.app import session_auth
from Gradex_AI_Server.app.core.database import db_instance
from Gradex_AI_Server.app.main import app

ORIGIN = {"Origin": "http://localhost:5173"}
LECTURER_A = {"email": "a@uni.lk", "role": "lecturer", "student_id": None}
LECTURER_B = {"email": "b@uni.lk", "role": "lecturer", "student_id": None}
STUDENT = {"email": "s@uni.lk", "role": "student", "student_id": "IT22000001"}


def _matches(doc, query):
    for key, cond in query.items():
        value = doc.get(key)
        if isinstance(cond, dict) and "$in" in cond:
            if value not in cond["$in"]:
                return False
        elif value != cond:
            return False
    return True


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, length=None):
        return list(self.docs)


class FakeCol:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        doc.setdefault("_id", ObjectId())
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    async def find_one(self, query):
        return next((d for d in self.docs if _matches(d, query)), None)

    def find(self, query=None):
        return _Cursor([d for d in self.docs if _matches(d, query or {})])

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if doc:
            doc.update(update.get("$set", {}))
        return SimpleNamespace(matched_count=1 if doc else 0)

    async def create_index(self, *_a, **_k):
        return None

    async def aggregate(self, pipeline):
        match = pipeline[0]["$match"]
        groups = {}
        for doc in self.docs:
            if _matches(doc, match):
                row = groups.setdefault(doc["viva_id"], {"_id": doc["viva_id"], "total": 0, "published": 0})
                row["total"] += 1
                row["published"] += 1 if doc.get("published") is True else 0
        for row in groups.values():
            yield row


FAKE_RESULT = {
    "video_status": "success",
    "confidence_score": 70,
    "engagement_score": 70,
    "assessment": {"status": "VALID", "final_score": 70, "scoring_version": "v1", "ai_performance": {"score": 70}},
}


class VivaFlowHttpTests(unittest.TestCase):
    def setUp(self):
        self.vivas = FakeCol()
        self.marks = FakeCol()
        self.user = LECTURER_A
        self.rubrics = {"Cs3021": {"subject_code": "Cs3021", "concepts": [{"id": "c1", "name": "x"}]}}

        async def fake_session_user(_connection):
            return self.user

        async def fake_ensure():
            return True

        async def fake_get_rubric(_db, code):
            return self.rubrics.get(code)

        self._saved = (db_instance.db, db_instance.marks_col, db_instance.client)
        db_instance.db = {"viva_sessions": self.vivas}
        db_instance.marks_col = self.marks
        db_instance.client = None
        for p in (
            patch.object(session_auth, "session_user", fake_session_user),
            patch("Gradex_AI_Server.app.auth.session_user", fake_session_user),
            patch("Gradex_AI_Server.app.viva_sessions.ensure_marks_collection", fake_ensure),
            patch("Gradex_AI_Server.app.core.database.ensure_marks_collection", fake_ensure),
            patch("Gradex_AI_Server.app.subject_rubric_service.get_subject_rubric", fake_get_rubric),
            patch("Gradex_AI_Server.app.viva_service.analyze_video_file", lambda *_a, **_k: dict(FAKE_RESULT)),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self._restore)
        self.client = TestClient(app, headers=ORIGIN)

    def _restore(self):
        db_instance.db, db_instance.marks_col, db_instance.client = self._saved

    def _viva(self, **overrides):
        body = {
            "name": "ER Viva",
            "subject_code": "SE3040",
            "subject_name": "Software Testing",
            "category": "non_technical",
            "year": 2026,
            "semester": 2,
        }
        body.update(overrides)
        return self.client.post("/api/vivas", json=body)

    def _upload(self, viva_id, student_id="IT22000001", **extra):
        data = {"student_id": student_id, **extra}
        if viva_id is not None:
            data["viva_id"] = viva_id
        return self.client.post(
            "/api/viva-analyze",
            data=data,
            files={"video": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
        )

    # --- creation -------------------------------------------------------
    def test_create_returns_label_and_mode(self):
        response = self._viva()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["label"], "SE3040-ER Viva - semester 2 - 2026")
        self.assertEqual(body["assessment_mode"], "WITHOUT_TECHNICAL_ACCURACY")
        self.assertEqual(body["examiner_email"], "a@uni.lk")

    def test_create_validation(self):
        for bad in (
            {"name": ""},
            {"subject_code": ""},
            {"subject_name": ""},
            {"category": "other"},
            {"year": 1999},
            {"semester": 0},
            {"semester": 9},
        ):
            self.assertEqual(self._viva(**bad).status_code, 422, bad)

    def test_whitespace_only_fields_rejected(self):
        self.assertEqual(self._viva(name="   ").status_code, 400)

    def test_technical_viva_keeps_code_case(self):
        ok = self._viva(category="technical", subject_code="Cs3021")
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["subject_code"], "Cs3021")
        self.assertEqual(ok.json()["assessment_mode"], "WITH_TECHNICAL_ACCURACY")

    def test_technical_viva_blocked_until_subject_content_added(self):
        """Create first, add the subject content right after, then analyze."""
        viva = self._viva(category="technical", subject_code="NEW101")
        self.assertEqual(viva.status_code, 200, viva.text)
        blocked = self._upload(viva.json()["viva_id"])
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("subject content", blocked.json()["detail"])
        self.assertEqual(self.marks.docs, [])
        self.rubrics["NEW101"] = {"subject_code": "NEW101", "concepts": [{"id": "c1", "name": "x"}]}
        ok = self._upload(viva.json()["viva_id"])
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertFalse(ok.json()["published"])

    # --- access control -------------------------------------------------
    def test_students_cannot_use_vivas(self):
        self.user = STUDENT
        self.assertEqual(self.client.get("/api/vivas").status_code, 403)
        self.assertEqual(self._viva().status_code, 403)

    def test_untrusted_origin_rejected_on_create(self):
        response = TestClient(app, headers={"Origin": "http://evil.example"}).post("/api/vivas", json={})
        self.assertEqual(response.status_code, 403)

    # --- analysis -------------------------------------------------------
    def test_analyze_requires_viva_and_student(self):
        self.assertEqual(self._upload(None).status_code, 400)
        self.assertEqual(self._upload(str(ObjectId())).status_code, 404)
        viva = self._viva().json()
        self.assertEqual(self._upload(viva["viva_id"], student_id="").status_code, 400)
        self.assertEqual(self._upload("not-an-id").status_code, 400)

    def test_analyze_files_mark_under_viva(self):
        viva = self._viva().json()
        response = self._upload(viva["viva_id"])
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["assessment_mode"], "WITHOUT_TECHNICAL_ACCURACY")
        self.assertTrue(body["published"], "non-technical vivas auto-publish")
        stored = self.marks.docs[0]
        self.assertEqual(stored["viva_id"], viva["viva_id"])
        self.assertEqual(stored["viva_label"], viva["label"])
        self.assertEqual(stored["subject_code"], "SE3040")
        self.assertEqual(stored["student_id"], "IT22000001")
        self.assertEqual(stored["examiner_email"], "a@uni.lk")

    def test_client_cannot_override_mode_or_subject(self):
        viva = self._viva().json()
        response = self._upload(
            viva["viva_id"], assessment_mode="WITH_TECHNICAL_ACCURACY", subject_code="HACK"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["assessment_mode"], "WITHOUT_TECHNICAL_ACCURACY")
        self.assertEqual(self.marks.docs[0]["subject_code"], "SE3040")

    def test_technical_viva_stays_draft(self):
        viva = self._viva(category="technical", subject_code="Cs3021").json()
        response = self._upload(viva["viva_id"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["published"])
        self.assertEqual(self.marks.docs[0]["subject_code"], "Cs3021")

    def test_other_lecturer_cannot_analyze_under_my_viva(self):
        viva = self._viva().json()
        self.user = LECTURER_B
        self.assertEqual(self._upload(viva["viva_id"]).status_code, 403)
        self.assertEqual(self.marks.docs, [])

    # --- listing --------------------------------------------------------
    def test_list_scoping_filters_and_counts(self):
        a1 = self._viva().json()
        self._viva(name="Tech", category="technical", subject_code="Cs3021")
        self._upload(a1["viva_id"])
        self.user = LECTURER_B
        self._viva(name="Bs viva", subject_code="IT1010", subject_name="Intro")

        self.user = LECTURER_A
        mine = self.client.get("/api/vivas").json()
        self.assertEqual({v["name"] for v in mine["items"]}, {"ER Viva", "Tech"})
        by_name = {v["name"]: v for v in mine["items"]}
        self.assertEqual(by_name["ER Viva"]["mark_count"], 1)
        self.assertEqual(by_name["ER Viva"]["published_count"], 1)
        self.assertEqual(by_name["Tech"]["mark_count"], 0)

        everyone = self.client.get("/api/vivas?all=true").json()
        self.assertEqual(everyone["count"], 3)
        tech = self.client.get("/api/vivas?category=technical").json()
        self.assertEqual([v["name"] for v in tech["items"]], ["Tech"])
        subject = self.client.get("/api/vivas?all=true&subject_code=IT1010").json()
        self.assertEqual([v["name"] for v in subject["items"]], ["Bs viva"])
        self.assertEqual(self.client.get("/api/vivas?category=bogus").status_code, 422)

    def test_get_viva(self):
        viva = self._viva().json()
        self.assertEqual(self.client.get(f"/api/vivas/{viva['viva_id']}").json()["label"], viva["label"])
        self.assertEqual(self.client.get(f"/api/vivas/{ObjectId()}").status_code, 404)
        self.assertEqual(self.client.get("/api/vivas/zzz").status_code, 400)

    def test_marks_filter_by_viva_and_published_by(self):
        v1 = self._viva().json()
        v2 = self._viva(name="Second").json()
        self._upload(v1["viva_id"], student_id="IT22000001")
        self._upload(v2["viva_id"], student_id="IT22000002")
        listed = self.client.get(f"/api/viva-marks?viva_id={v1['viva_id']}").json()
        self.assertEqual(listed["count"], 1)
        row = listed["items"][0]
        self.assertEqual(row["student_id"], "IT22000001")
        self.assertEqual(row["viva_label"], v1["label"])
        self.assertEqual(row["examiner_email"], "a@uni.lk")

        self.user = LECTURER_B
        self.assertEqual(self.client.get("/api/viva-marks?mine=true").json()["count"], 0)
        self.user = LECTURER_A
        self.assertEqual(self.client.get("/api/viva-marks?mine=true").json()["count"], 2)

    def test_publish_records_publisher(self):
        viva = self._viva(category="technical", subject_code="Cs3021").json()
        mark_id = self._upload(viva["viva_id"]).json()["mark_id"]
        response = self.client.patch(
            f"/api/viva-marks/{mark_id}/publish",
            json={"assessment_mode": "WITH_TECHNICAL_ACCURACY", "technical_accuracy": 8, "published": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.marks.docs[0]["published_by"], "a@uni.lk")
        self.assertTrue(self.marks.docs[0]["published"])

    # --- live copilot ---------------------------------------------------
    def _live(self, session_id, viva_id=None, student_id="IT22000001"):
        data = {}
        if viva_id is not None:
            data["viva_id"] = viva_id
        if student_id is not None:
            data["student_id"] = student_id
        return self.client.post(
            f"/api/viva-copilot/sessions/{session_id}/analyze",
            data=data,
            files={"video": ("live.webm", b"fake-recording", "video/webm")},
        )

    def test_live_analyze_requires_viva_and_student_then_files_mark(self):
        session_id = self.client.post("/api/viva-copilot/sessions", json={}).json()["sessionId"]
        viva = self._viva().json()
        self.assertEqual(self._live(session_id, None).status_code, 400)
        self.assertEqual(self._live(session_id, viva["viva_id"], student_id="").status_code, 400)
        self.assertEqual(self._live(session_id, str(ObjectId())).status_code, 404)
        self.assertEqual(self.marks.docs, [])

        response = self._live(session_id, viva["viva_id"])
        self.assertEqual(response.status_code, 200, response.text)
        stored = self.marks.docs[0]
        self.assertEqual(stored["source"], "live_copilot")
        self.assertEqual(stored["viva_id"], viva["viva_id"])
        self.assertEqual(stored["student_id"], "IT22000001")
        self.assertEqual(stored["examiner_email"], "a@uni.lk")

    def test_live_analyze_rejects_other_lecturers_viva(self):
        viva = self._viva().json()
        self.user = LECTURER_B
        session_id = self.client.post("/api/viva-copilot/sessions", json={}).json()["sessionId"]
        self.assertEqual(self._live(session_id, viva["viva_id"]).status_code, 403)

    # --- duplicates & validation ---------------------------------------
    def test_duplicate_viva_blocked_per_lecturer(self):
        self.assertEqual(self._viva().status_code, 200)
        again = self._viva(name="  er   VIVA ")
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(len(self.vivas.docs), 1)
        # Different semester / year / subject are different vivas.
        self.assertEqual(self._viva(semester=1).status_code, 200)
        self.assertEqual(self._viva(year=2027).status_code, 200)
        self.assertEqual(self._viva(subject_code="SE3050").status_code, 200)
        # Another lecturer may reuse the same details.
        self.user = LECTURER_B
        self.assertEqual(self._viva().status_code, 200)

    def test_semesters_one_to_four(self):
        for semester in (1, 2, 3, 4):
            self.assertEqual(self._viva(semester=semester).status_code, 200, semester)
        self.assertEqual(self._viva(semester=5).status_code, 422)

    def test_student_id_format_enforced_and_normalised(self):
        viva = self._viva().json()
        for bad in ("IT0001", "22557056", "ITABCDEFGH", "IT225570561", "IT 22557056", "STU-001"):
            response = self._upload(viva["viva_id"], student_id=bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn("IT22557056", response.json()["detail"])
        self.assertEqual(self.marks.docs, [])
        ok = self._upload(viva["viva_id"], student_id=" it22557056 ")
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(self.marks.docs[0]["student_id"], "IT22557056")

    def test_student_id_format_enforced_on_live_and_mark_edits(self):
        viva = self._viva().json()
        session_id = self.client.post("/api/viva-copilot/sessions", json={}).json()["sessionId"]
        self.assertEqual(self._live(session_id, viva["viva_id"], student_id="bad").status_code, 400)
        mark_id = self._upload(viva["viva_id"]).json()["mark_id"]
        self.assertEqual(
            self.client.patch(f"/api/viva-marks/{mark_id}/student", json={"student_id": "nope"}).status_code, 400
        )
        fixed = self.client.patch(f"/api/viva-marks/{mark_id}/student", json={"student_id": "it22000009"})
        self.assertEqual(fixed.json()["student_id"], "IT22000009")

    def test_same_student_twice_needs_confirmation(self):
        viva = self._viva().json()
        self.assertEqual(self._upload(viva["viva_id"]).status_code, 200)
        second = self._upload(viva["viva_id"])
        self.assertEqual(second.status_code, 409, second.text)
        self.assertIn("already has a mark", second.json()["detail"])
        self.assertEqual(len(self.marks.docs), 1)
        # A different student, or a confirmed re-analysis, goes through.
        self.assertEqual(self._upload(viva["viva_id"], student_id="IT22000002").status_code, 200)
        confirmed = self._upload(viva["viva_id"], allow_duplicate="true")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(len(self.marks.docs), 3)

    def test_same_student_in_another_viva_is_fine(self):
        first = self._viva().json()
        second = self._viva(name="Other").json()
        self.assertEqual(self._upload(first["viva_id"]).status_code, 200)
        self.assertEqual(self._upload(second["viva_id"]).status_code, 200)

    def test_live_duplicate_needs_confirmation(self):
        viva = self._viva().json()
        self._upload(viva["viva_id"])
        session_id = self.client.post("/api/viva-copilot/sessions", json={}).json()["sessionId"]
        self.assertEqual(self._live(session_id, viva["viva_id"]).status_code, 409)
        response = self.client.post(
            f"/api/viva-copilot/sessions/{session_id}/analyze",
            data={"viva_id": viva["viva_id"], "student_id": "IT22000001", "allow_duplicate": "true"},
            files={"video": ("live.webm", b"fake-recording", "video/webm")},
        )
        self.assertEqual(response.status_code, 200, response.text)

    # --- the marking scale is configuration ----------------------------
    def test_viva_config_shares_the_scale_with_the_client(self):
        from VivaEvaluationEngine.services.assessment_scoring import MARKING_SCALE

        config = self.client.get("/api/viva-config").json()
        self.assertEqual(config["mark_max"], MARKING_SCALE.mark_max)
        self.assertEqual(config["technical_max"], MARKING_SCALE.technical_max)
        self.assertEqual(config["decimals"], MARKING_SCALE.decimals)
        grades = [band["grade"] for band in config["grade_bands"]]
        self.assertEqual(grades[0], "A+")
        self.assertEqual(grades[-1], "F")
        self.assertEqual(config["grade_bands"][0]["min_mark"], MARKING_SCALE.mark_max * 0.9)

    def test_viva_config_requires_a_lecturer(self):
        self.user = STUDENT
        self.assertEqual(self.client.get("/api/viva-config").status_code, 403)

    # --- marks are on the configured scale -------------------------------------------
    def _real_analysis(self, mode="WITHOUT_TECHNICAL_ACCURACY"):
        """An analysis result with real engine inputs, so the engine produces a mark."""
        import copy

        from Gradex_AI_Server.app.tests.test_viva_publish_technical import _engine_result
        from VivaEvaluationEngine.services.assessment_scoring import build_assessment

        result = _engine_result()
        result["assessment"] = build_assessment(result, mode=mode)
        return patch(
            "Gradex_AI_Server.app.viva_service.analyze_video_file",
            lambda *_a, **_k: copy.deepcopy(result),
        )

    def test_non_technical_mark_is_on_the_configured_scale_with_matching_grade(self):
        from VivaEvaluationEngine.services.assessment_scoring import MARKING_SCALE, resolve_grade_from_mark

        viva = self._viva().json()
        with self._real_analysis():
            body = self._upload(viva["viva_id"]).json()
        self.assertIsNotNone(body["final_mark"])
        self.assertEqual(body["final_mark_max"], MARKING_SCALE.mark_max)
        self.assertLessEqual(body["final_mark"], MARKING_SCALE.mark_max)
        self.assertEqual(body["final_mark"], MARKING_SCALE.percent_to_mark(body["final_score"]))
        self.assertEqual(body["final_grade"], resolve_grade_from_mark(body["final_mark"]))
        row = self.client.get("/api/viva-marks").json()["items"][0]
        self.assertEqual(row["final_mark"], body["final_mark"])
        self.assertEqual(row["final_mark_max"], MARKING_SCALE.mark_max)
        self.assertEqual(row["final_grade"], body["final_grade"])

    def test_each_viva_is_marked_out_of_its_own_total(self):
        from VivaEvaluationEngine.services.assessment_scoring import MARKING_SCALE

        marks = {}
        for total in (None, 50, 100):
            extra = {} if total is None else {"total_marks": total}
            viva = self._viva(name=f"Viva {total}", **extra).json()
            self.assertEqual(viva["total_marks"], total or MARKING_SCALE.mark_max)
            with self._real_analysis():
                body = self._upload(viva["viva_id"]).json()
            self.assertEqual(body["final_mark_max"], total or MARKING_SCALE.mark_max)
            self.assertEqual(body["assessment"]["final_mark_max"], total or MARKING_SCALE.mark_max)
            marks[total] = body
        # Same recording, so the same percentage; only the scale changes.
        percent = marks[None]["final_score"]
        self.assertEqual(marks[50]["final_score"], percent)
        self.assertEqual(marks[50]["final_mark"], round(percent / 100 * 50, 2))
        self.assertEqual(marks[100]["final_mark"], round(percent, 2))
        self.assertLessEqual(marks[50]["final_mark"], 50)

    def test_technical_publish_is_out_of_the_viva_total(self):
        viva = self._viva(category="technical", subject_code="Cs3021", total_marks=50).json()
        with self._real_analysis("WITH_TECHNICAL_ACCURACY"):
            mark_id = self._upload(viva["viva_id"]).json()["mark_id"]
        url = f"/api/viva-marks/{mark_id}/publish"
        too_high = self.client.patch(
            url, json={"assessment_mode": "WITH_TECHNICAL_ACCURACY", "technical_accuracy": 51, "published": True}
        )
        self.assertEqual(too_high.status_code, 422)
        ok = self.client.patch(
            url, json={"assessment_mode": "WITH_TECHNICAL_ACCURACY", "technical_accuracy": 45, "published": True}
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertEqual(body["final_mark_max"], 50)
        self.assertEqual(body["technical_accuracy"], 45)
        self.assertLessEqual(body["final_mark"], 50)

    def test_total_marks_must_be_positive(self):
        for bad in (0, -5, 1001):
            self.assertEqual(self._viva(name=f"Bad {bad}", total_marks=bad).status_code, 422, bad)

    def test_technical_publish_takes_a_score_out_of_the_technical_maximum(self):
        from VivaEvaluationEngine.services.assessment_scoring import MARKING_SCALE, resolve_grade_from_mark

        technical_max = MARKING_SCALE.technical_max
        entered = round(technical_max * 0.9, 2)

        viva = self._viva(category="technical", subject_code="Cs3021").json()
        with self._real_analysis("WITH_TECHNICAL_ACCURACY"):
            mark_id = self._upload(viva["viva_id"]).json()["mark_id"]
        too_high = self.client.patch(
            f"/api/viva-marks/{mark_id}/publish",
            json={"assessment_mode": "WITH_TECHNICAL_ACCURACY", "technical_accuracy": technical_max + 1, "published": True},
        )
        self.assertEqual(too_high.status_code, 422)
        ok = self.client.patch(
            f"/api/viva-marks/{mark_id}/publish",
            json={"assessment_mode": "WITH_TECHNICAL_ACCURACY", "technical_accuracy": entered, "published": True},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        data = ok.json()
        self.assertEqual(data["technical_accuracy"], entered)
        self.assertEqual(data["final_mark_max"], MARKING_SCALE.mark_max)
        self.assertEqual(data["final_mark"], MARKING_SCALE.percent_to_mark(data["final_score"]))
        self.assertEqual(data["final_grade"], resolve_grade_from_mark(data["final_mark"]))

    # --- resume banner: reattach to a running analysis ------------------
    def test_progress_survives_the_uploading_connection(self):
        """A reloaded page has no upload request any more; it must still be able to
        find the running job by its progress id and then see it finish with the mark id."""
        import threading
        import time

        viva = self._viva().json()
        release = threading.Event()
        started = threading.Event()

        def slow_analysis(*_args, **_kwargs):
            started.set()
            release.wait(timeout=10)
            return dict(FAKE_RESULT)

        outcome = {}

        def upload():
            with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", slow_analysis):
                outcome["response"] = TestClient(app, headers=ORIGIN).post(
                    "/api/viva-analyze",
                    data={"viva_id": viva["viva_id"], "student_id": "IT22000001", "progress_id": "resume-job-1"},
                    files={"video": ("clip.mp4", b"fake-video-bytes", "video/mp4")},
                )

        # Patches are process-wide, so start the slow upload under its own patch.
        worker = threading.Thread(target=upload)
        worker.start()
        self.assertTrue(started.wait(timeout=10), "analysis never started")

        # The "reloaded page": a brand-new client that never saw the upload.
        reloaded = TestClient(app, headers=ORIGIN)
        running = reloaded.get("/api/viva-analyze/progress/resume-job-1").json()
        self.assertTrue(running["stage"], "job should be visible while running")
        self.assertFalse(running["finished"])

        release.set()
        worker.join(timeout=15)
        self.assertEqual(outcome["response"].status_code, 200, outcome["response"].text)

        deadline = time.time() + 5
        done = reloaded.get("/api/viva-analyze/progress/resume-job-1").json()
        while not done["finished"] and time.time() < deadline:
            time.sleep(0.1)
            done = reloaded.get("/api/viva-analyze/progress/resume-job-1").json()
        self.assertTrue(done["finished"])
        self.assertEqual(done["mark_id"], outcome["response"].json()["mark_id"])

        # The stream a reattached banner opens ends straight away for a finished job.
        with reloaded.stream("GET", "/api/viva-analyze/progress/resume-job-1/stream") as stream:
            body = "".join(stream.iter_text())
        self.assertIn("event: done", body)

    def test_unknown_progress_id_reads_as_lost(self):
        """The banner shows 'Could not reconnect' when there is no stage and version 0."""
        snapshot = self.client.get("/api/viva-analyze/progress/never-existed").json()
        self.assertFalse(snapshot.get("stage"))
        self.assertFalse(snapshot.get("version"))
        self.assertFalse(snapshot.get("finished"))

    def test_progress_requires_a_lecturer(self):
        self.user = STUDENT
        self.assertEqual(self.client.get("/api/viva-analyze/progress/x").status_code, 403)


if __name__ == "__main__":
    unittest.main()
