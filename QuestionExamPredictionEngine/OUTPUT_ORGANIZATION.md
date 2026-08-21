# Output Organization Guide

## New Folder Structure

The QuestionExamPredictionEngine now organizes outputs by **year** and **exam session** to prevent data loss and keep analyses organized.

### Folder Hierarchy
```
output/
├── 2024/
│   └── PAPERS/
│       ├── 20250511_120000/  (First run - timestamp)
│       │   ├── student_report.json
│       │   ├── student_summary.json
│       │   ├── misunderstood_questions.json
│       │   ├── cognitive_gap_analysis.json
│       │   └── weak_topics.json
│       │
│       └── 20250511_153000/  (Second run - timestamp)
│           ├── student_report.json
│           ├── student_summary.json
│           ├── misunderstood_questions.json
│           ├── cognitive_gap_analysis.json
│           └── weak_topics.json
│
└── 2025/
    └── PAPERS/
        └── 20250511_154500/
            └── [all output files]
```

## How It Works

1. **Year Folder**: Automatically extracted from student data (`student.get("year")`)
2. **Exam Folder**: Automatically extracted from student data (`student.get("exam")`)
3. **Timestamp Subfolder**: Each run creates a unique subfolder with format `YYYYMMDD_HHMMSS`

## Key Features

✅ **No Data Loss**: Previous analyses are never overwritten  
✅ **Easy Tracking**: Each run has its own timestamp folder  
✅ **Organized by Exam**: Group results by year and exam session  
✅ **Scalable**: Can run multiple analyses and keep all results  

## Example Usage

When you run the analysis with exam data containing:
```json
{
  "student_id": "S001",
  "year": 2025,
  "exam": "Papers",
  "answers": [...]
}
```

Output will be saved to:
```
output/2025/Papers/20250511_160000/
```

## Student Data Format

Ensure your `student_answers.json` includes these fields:
```json
{
  "student_id": "S001",
  "year": 2025,
  "exam": "Papers",
  "answers": [...]
}
```

The system will use these to organize outputs automatically!
