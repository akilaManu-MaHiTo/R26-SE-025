from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.api import deps, lecturer
from app.classifier.rules import classify_by_rules
from app.ingestion.student_data import normalize_student_submission
from app.llm.roles.student_analysis import QuestionSemantics
from app.services import student_pipeline
from app.taxonomy.normalizer import load_taxonomy_sync
from tests.test_student_data_ingestion import minimal_course, minimal_rubric, minimal_submission


@pytest.mark.parametrize('text, expected', [
    ('Database Design Phases, Weak Entities, and Ternary Relationships', 'Introduction to DBMS & Conceptual Database Design'),
    ('Schema Refinement and Anomalies', 'Schema Refinement'),
    ('Views, Advantages, and Limitations', 'Database Programming'),
    ('Attribute Closure and Key Determination', 'Schema Refinement'),
    ('SQL Server Security Authorization Steps', 'Database Security'),
])
def test_2026_question_titles_resolve_to_course_topics(text, expected):
    result = classify_by_rules(text, bloom_level='Understand', taxonomy=load_taxonomy_sync('IT2040'))
    assert result.topic_assignments[0].topic == expected


def test_course_subtopic_phrases_are_used_without_importing_dbms_topics():
    taxonomy = {'scheduling': {'canonical_topic': 'Scheduling', 'aliases': [], 'subtopics': ['Round Robin']}}
    assert classify_by_rules('Explain Round Robin', bloom_level='Understand', taxonomy=taxonomy).topic_assignments[0].topic == 'Scheduling'
    assert classify_by_rules('Write SQL SELECT', bloom_level='Apply', taxonomy=taxonomy).topic_assignments[0].topic == 'Unclassified'


def test_equal_topic_evidence_remains_unclassified():
    taxonomy = {key: {'canonical_topic': key, 'aliases': ['shared phrase']} for key in ['Topic A', 'Topic B']}
    assert classify_by_rules('Explain shared phrase', bloom_level='Understand', taxonomy=taxonomy).topic_assignments[0].topic == 'Unclassified'


@pytest.mark.parametrize('text, topic', [
    ('Explain triggers.', 'Database Programming'),
    ('Explain stored procedures.', 'Database Programming'),
    ('Explain cursors.', 'Database Programming'),
    ('Explain primary keys.', 'Logical Database Design'),
    ('Explain joins.', 'Structured Query Language (SQL)'),
])
def test_plural_topic_terms_keep_their_assignment(text, topic):
    assert classify_by_rules(text, bloom_level='Understand').topic_assignments[0].topic == topic


@pytest.mark.parametrize('score', [1, 5])
def test_pending_topics_are_not_student_strengths_weaknesses_or_recommendations(score):
    from app.analytics.student_document import build_numeric_analysis
    normalized = normalize_student_submission(minimal_course(), minimal_rubric(), minimal_submission('01', score, 5))
    semantics = {'01': QuestionSemantics(level='Understand', topic='Unclassified', subtopic='Unclassified', confidence=.8, reason='source=unclassified_no_match')}
    result = build_numeric_analysis(normalized, semantics)
    assert result.overall_performance.score == score
    assert result.question_performance[0].performance.score == score
    assert result.learning_analysis.strong_topics == []
    assert result.learning_analysis.critical_topics == []
    assert result.learning_analysis.learning_gaps == []
    assert result.recommendations == []
    assert result.next_question_strategy.recommended_topics == []


def test_unclassified_marks_remain_in_statistics_but_not_topic_claims():
    student = {
        'overall': {'score': 2, 'maximum': 10, 'percentage': 20},
        'topic_performance': [{'topic': 'Unclassified', 'score': 2, 'max_score': 10}],
        'bloom_performance': [],
        'question_performance': [{'question_no': '01', 'topic': 'Unclassified', 'bloom_level': 'Understand', 'score': 2, 'max_score': 10}],
    }
    result = compute_exam_analytics_stats([student], .5)
    assert result['statistics']['average_percentage'] == 20
    assert result['bloom_performance'][0]['average_percentage'] == 20
    assert result['question_performance'][0]['average_percentage'] == 20
    assert not result['attention_areas']
    assert not any('Unclassified' in text and ('weakest' in text or 'strongest' in text) for text in result['insights'])


@pytest.mark.parametrize('score', [0, 10])
def test_many_unclassified_attempts_do_not_establish_topic_strength_or_weakness(score):
    student = {'overall': {'score': score * 2, 'maximum': 20, 'percentage': score * 10},
               'topic_performance': [{'topic': 'Unclassified', 'score': score * 2, 'max_score': 20}],
               'bloom_performance': [],
               'question_performance': [{'question_no': str(i), 'topic': 'Unclassified', 'bloom_level': 'Understand', 'score': score, 'max_score': 10} for i in [1, 2]]}
    result = compute_exam_analytics_stats([student] * 12, .5)
    assert result['topic_performance'][0]['evidence_status'] == 'insufficient_evidence'
    assert result['topic_bloom_matrix'][0]['evidence_status'] == 'insufficient_evidence'


def test_normalizer_preserves_lecturer_topic_metadata():
    rubric = minimal_rubric()
    rubric['questions'][0]['approved_topic'] = 'Schema Refinement'
    normalized = normalize_student_submission(minimal_course(), rubric, minimal_submission('01', 3, 5))
    assert normalized.questions[0].approved_topic == 'Schema Refinement'


@pytest.mark.parametrize('force_reclassify', [False, True])
async def test_approved_topic_overrides_classification_without_leaking_to_text_cache(monkeypatch, force_reclassify):
    monkeypatch.setattr(student_pipeline, 'classify_question_semantics', None)
    base = QuestionSemantics(level='Analyze', topic='Unclassified', subtopic='Unclassified', confidence=.8, reason='source=unclassified_no_match')
    cache = {('rubric-a', '01'): base}
    question = SimpleNamespace(question_no='01', question_text='Same question', approved_topic='Schema Refinement')
    normalized = SimpleNamespace(course_code='IT2040', rubric_ref='rubric-a', questions=[question])
    result = await student_pipeline._classify_questions(normalized, cache, force_reclassify=force_reclassify)
    assert result['01'].topic == 'Schema Refinement'
    assert result['01'].level == 'Analyze'
    assert 'source=lecturer' in result['01'].reason
    question.approved_topic = None
    result = await student_pipeline._classify_questions(normalized, cache)
    assert result['01'].topic == 'Unclassified'


@pytest.mark.parametrize('single_prediction', [False, True])
async def test_current_topic_cache_is_reused_without_persisting_lecturer_overrides(monkeypatch, single_prediction):
    from app.classifier import bloom_classifier
    entries = {}
    calls = []
    class Cache:
        async def find_one(self, query):
            return entries.get(query['cache_key'])
        async def update_one(self, query, update, **kwargs):
            entries[query['cache_key']] = update['$set']
    async def taxonomy(*args):
        return {}
    monkeypatch.setattr('app.taxonomy.normalizer.load_taxonomy', taxonomy)
    def predict(text):
        calls.append(text)
        return {'level': 'Analyze', 'label': 'BT4', 'confidence': .9}
    monkeypatch.setattr(bloom_classifier, 'is_bloom_model_available', lambda: True)
    if single_prediction:
        monkeypatch.setattr(bloom_classifier, 'predict_bloom', predict)
    else:
        monkeypatch.setattr(bloom_classifier, 'predict_bloom_batch', lambda texts: [predict(text) for text in texts])
    normalized = SimpleNamespace(course_code='IT2040', rubric_ref='rubric-a', questions=[
        SimpleNamespace(question_no='01', question_text='Unknown subject', approved_topic='Schema Refinement')])
    db = {'bloom_classification_cache': Cache()}
    result = await student_pipeline._classify_questions(normalized, {}, db=db)
    assert result['01'].topic == 'Schema Refinement'
    normalized.rubric_ref = 'rubric-b'
    normalized.questions[0].approved_topic = None
    result = await student_pipeline._classify_questions(normalized, {}, db=db)
    assert result['01'].topic == 'Unclassified'
    assert len(calls) == 1


class Collection:
    def __init__(self, documents):
        self.documents = documents

    async def find_one(self, query):
        return next((deepcopy(d) for d in self.documents if all(d.get(k) == v for k, v in query.items())), None)

    def find(self, query):
        rows = [deepcopy(d) for d in self.documents if all(d.get(k) == v for k, v in query.items())]

        class Cursor:
            async def to_list(self, length=None):
                return rows
        return Cursor()

    async def update_one(self, query, update):
        doc = next((d for d in self.documents if all(d.get(k) == v for k, v in query.items())), None)
        if doc:
            doc.update(deepcopy(update['$set']))
        return SimpleNamespace(matched_count=int(doc is not None))

    async def update_many(self, query, update):
        for doc in self.documents:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(deepcopy(update['$set']))


@pytest.fixture
def topic_api(monkeypatch):
    identity = dict(subject_code='IT2040', session_name='Final Examination', year=2026, month=10, semester=1)
    rubric = {**minimal_rubric(), **identity, '_id': 'rubric-current'}
    db = {'rubricCollection': Collection([rubric, {**deepcopy(rubric), '_id': 'rubric-old', 'year': 2024}]),
          'submissions': Collection([{**identity, 'status': 'graded', 'rubric_ref': 'rubric-current'}])}
    for collection in ['examAnalytics', 'analytics_snapshots', 'student_analytics', 'studentExamAnalysis']:
        db[collection] = Collection([{**identity}, {**identity, 'year': 2024}])
    async def taxonomy(*args):
        return {'schema_refinement': {'canonical_topic': 'Schema Refinement'}}
    monkeypatch.setattr('app.taxonomy.normalizer.load_taxonomy', taxonomy)
    app = FastAPI()
    app.include_router(lecturer.router, prefix='/api')
    app.dependency_overrides[deps.get_db] = lambda: db
    return app, db


URL = '/api/lecturers/exams/IT2040/Final%20Examination/questions/1/topic?year=2026&month=10&semester=1'


async def test_topic_approval_is_saved_only_on_selected_rubric_and_can_be_cleared(topic_api):
    app, db = topic_api
    before = deepcopy(db['rubricCollection'].documents)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        saved = await client.put(URL, json={'topic': 'Schema Refinement'})
        assert saved.status_code == 200
        assert db['rubricCollection'].documents[0]['questions'][0]['approved_topic'] == 'Schema Refinement'
        assert db['rubricCollection'].documents[1] == before[1]
        assert db['rubricCollection'].documents[0]['questions'][0]['criteria'] == before[0]['questions'][0]['criteria']
        for collection in ['examAnalytics', 'analytics_snapshots', 'student_analytics', 'studentExamAnalysis']:
            assert db[collection].documents[0]['topic_assignment_pending'] is True
            assert 'topic_assignment_pending' not in db[collection].documents[1]
        cleared = await client.put(URL, json={'topic': None})
        assert cleared.status_code == 200
        assert db['rubricCollection'].documents[0]['questions'][0].get('approved_topic') is None


@pytest.mark.parametrize('url, payload, status', [
    (URL, {'topic': 'Invented topic'}, 422),
    (URL, {'topic': 'Unclassified'}, 422),
    (URL, {'topic': '   '}, 422),
    (URL, {}, 422),
    (URL.split('?')[0], {'topic': 'Schema Refinement'}, 422),
    (URL.replace('questions/1/', 'questions/99/'), {'topic': 'Schema Refinement'}, 404),
    (URL.replace('year=2026', 'year=2025'), {'topic': 'Schema Refinement'}, 404),
])
async def test_invalid_topic_or_exam_does_not_write(topic_api, url, payload, status):
    app, db = topic_api
    before = deepcopy(db['rubricCollection'].documents)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.put(url, json=payload)).status_code == status
    assert db['rubricCollection'].documents == before


async def test_pending_student_snapshot_is_rebuilt_after_topic_review(monkeypatch):
    from app.services import student_dashboard
    async def cached(*args):
        return {'analysis_version': student_pipeline.STUDENT_ANALYSIS_VERSION, 'topic_assignment_pending': True}
    async def missing_submission(*args):
        return None
    monkeypatch.setattr(student_dashboard, 'find_student_analytics', cached)
    monkeypatch.setattr(student_dashboard, 'find_graded_submission', missing_submission)
    with pytest.raises(student_dashboard.StudentNotFound):
        await student_dashboard.ensure_student_analytics({}, 'S1', 'IT2040', 'Final Examination')


@pytest.mark.parametrize('stream', [False, True])
async def test_lecturer_student_reads_rebuild_pending_snapshot(monkeypatch, stream):
    from unittest.mock import AsyncMock
    old = {'student_id': 'S1', 'analysis_version': student_pipeline.STUDENT_ANALYSIS_VERSION, 'topic_assignment_pending': True}
    fresh = {'student_id': 'S1', 'question_performance': [{'topic': 'Schema Refinement'}]}
    monkeypatch.setattr(lecturer, 'find_student_analytics', AsyncMock(return_value=old))
    monkeypatch.setattr(lecturer, 'find_graded_submission', AsyncMock(return_value={'evaluation': {'results': []}}))
    build = AsyncMock(return_value=fresh)
    monkeypatch.setattr(lecturer, 'ensure_student_analytics', build)
    # Diagram attachment is optional, independent evidence and may be absent.
    monkeypatch.setattr('app.db.repository.find_diagram_evaluation_for_student', AsyncMock(return_value=None))
    monkeypatch.setattr('app.db.repository.find_diagram_marking_for_student', AsyncMock(return_value=None))
    args = dict(course_code='IT2040', session_name='Final Examination', student_id='S1', year=2026, month=10, semester=1, include_ai_tips=True, db={})
    if stream:
        response = await lecturer.lecturer_student_detail_stream(**args)
        body = ''.join([chunk async for chunk in response.body_iterator])
        assert 'Schema Refinement' in body
    else:
        response = await lecturer.lecturer_student_detail(**args, auto_analyze=True)
        assert response['question_performance'][0]['topic'] == 'Schema Refinement'
    build.assert_awaited_once()


async def test_reanalysis_resolves_the_same_rubric_as_topic_review_with_string_reference():
    from bson import ObjectId
    from app.db.repository import find_rubric_for_submission
    ref = ObjectId('6accf43c3e55192d52a86dfe')
    old = {'_id': 'old', 'subject_code': 'IT2040', 'session_name': 'Final Examination', 'year': 2024}
    current = {**old, '_id': ref, 'year': 2026, 'questions': [{'approved_topic': 'Schema Refinement'}]}
    db = {'rubricCollection': Collection([old, current])}
    result = await find_rubric_for_submission(db, {**current, 'rubric_ref': str(ref)})
    assert result['_id'] == ref
    assert result['questions'][0]['approved_topic'] == 'Schema Refinement'


async def test_rubric_fallback_uses_complete_exam_identity():
    from app.db.repository import find_rubric_for_submission
    old = {'_id': 'old', 'subject_code': 'IT2040', 'session_name': 'Final Examination', 'year': 2024, 'month': 7, 'semester': 1}
    current = {**old, '_id': 'current', 'year': 2026, 'month': 10}
    db = {'rubricCollection': Collection([old, current])}
    result = await find_rubric_for_submission(db, {**current, 'rubric_ref': None})
    assert result['_id'] == 'current'
