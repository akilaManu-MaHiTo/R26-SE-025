# IT2040 synthetic research-panel demonstration

Exam key: `EXAM-IT2040-2022-S1-Jun-FINAL`.
50 fictitious students, all graded. Four essay questions at 20 marks each,
plus one diagram question at 20 marks: **100 marks per student**.

These are adapted repository fixtures, not the original examination paper or
real assessment evidence. Answers, marks and extracted diagram structures are
simulated. Every document carries `dataset_provenance`. The diagram structures
and grades are demonstration fixtures, not the output of running OCR or a grader
on submitted images. No student diagram image files are included.

## Files and collection counts

| File / requested collection | Documents | Purpose |
|---|---:|---|
| courses.json | 1 | IT2040 Database Management Systems |
| rubricCollection.json | 1 | Four essay questions, model answers, criteria, 50-student roster |
| submissions.json | 50 | Synthetic essay answers, criterion awards, totals out of 80 |
| diagram_marking.json | 1 | Shared question 05 and five marking criteria, total 20 |
| diagram_evaluation.json | 50 | Per-student diagram scores, feedback and simulated detections |

The diagram marking collection contains the shared marking scheme; individual
student marks belong in diagram_evaluation. Question 05 is excluded from essay
submissions and the essay rubric, preventing double counting.

`student_summary.json` is a presentation aid, not another database collection.
It lists essay marks, diagram marks, combined totals and essay question scores,
sorted by total. Totals range from 4 to 97; average 54.00. The score bands below
are descriptive bins, not university grade boundaries:

| Combined marks | Students |
|---|---:|
| 80–100 | 14 |
| 60–79 | 11 |
| 40–59 | 8 |
| 0–39 | 17 |

## Import and dashboard compatibility

The files are MongoDB Extended JSON arrays with deterministic ObjectIds.
Import with MongoDB Compass's JSON array support or `mongoimport --jsonArray`.
Use a separate disposable demo database: the exported records share the exam's
metadata with existing fixtures, so mixing them can create ambiguous results.
No database or application configuration is changed by the generator.

**Current analytics backend mapping:** import `diagram_evaluation.json` into
`diagram_evaluations` (plural). The other four file stems match the backend's
collection names. Importing only into the requested singular name will not make
diagrams appear in the current analytics dashboard.

The existing exam registry must contain this exam key with subjectCode IT2040,
examYear 2022, examMonth June, examSemester 1 and session Final. The backend checks
this registration when reading diagram results with examKey. Registry records
are outside the five requested collections and are not supplied or changed here.
After selecting the demo database, run the application's normal exam analysis
workflow to produce dashboard analytics. No precomputed analytics are included.

## Viva demonstration

Show the class distribution, then pick a high, middle and low scoring student
from student_summary.json. Compare question scores to explain how topic-specific
weaknesses can differ from the overall total. All 50 are complete; this dataset
does not demonstrate pending-grading behaviour. Describe Bloom classifications
and recommendations as engine outputs when you actually run the analysis;
stored labels and simulated marks are not measured model accuracy.

## Rebuild and validation

From AdaptiveExamAnalyticsEngine run:

```powershell
python scripts/build_viva_dataset.py
```

The script uses the existing sample_data_v4 JSON files, checks the exported BSON
forms through the real essay/diagram input normalizers, and asserts counts,
student/reference matching, valid criterion marks, totals, uniqueness and
synthetic labels before writing. It never connects to MongoDB.
The script overwrites this dedicated export's generated JSON files when rerun.
