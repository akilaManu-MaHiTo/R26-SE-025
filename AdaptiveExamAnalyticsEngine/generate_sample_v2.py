"""Generate IT2040 2024 Final Exam sample data for gradev2 database.

Exam structure:
  Q1 (20 marks) - EER Diagram → Relational Model  → diagram_evaluation + diagram_marking
  Q2 (15 marks) - Functional Dependencies           → submissions + rubricCollection
  Q3 (25 marks) - Relational Algebra                → submissions + rubricCollection
  Q4 (40 marks) - SQL                               → submissions + rubricCollection
  Total: 100 marks (Q1=20 diagram + Q2-Q4=80 theory)

10 students with IT22xxxx IDs, each sitting the same IT2040 exam.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

OUT_DIR = Path(__file__).resolve().parent / "app" / "sample_data" / "sample_data_v2"

# ── 10 Students (ranked top → low) ──────────────────────────────────────
STUDENT_IDS = [
    "IT22262551",  # 1st  - Top (100/100)
    "IT22262552",  # 2nd  - Excellent (93/100)
    "IT22262553",  # 3rd  - Good (85/100)
    "IT22262554",  # 4th  - Good (78/100)
    "IT22262555",  # 5th  - Average (67/100)
    "IT22262556",  # 6th  - Below Average (55/100)
    "IT22262557",  # 7th  - Weak (43/100)
    "IT22262558",  # 8th  - Poor (35/100)
    "IT22262559",  # 9th  - Very Poor (25/100)
    "IT22262560",  # 10th - Failing (15/100)
]

SUBJECT_CODE = "IT2040"
SUBJECT_NAME = "Database Management Systems"
YEAR = 2024
MONTH = 7
SEMESTER = 1
SESSION_NAME = "Final Examination"
EXAM_CODE = "EER-001"  # for diagram evaluation

# ── Q1 Diagram Criteria (based on the EER diagram in the PDF) ───────────
# Person(superclass): SSN(PK), Name, Address
# Instructor(subclass): Rank, Salary
# Researcher(subclass): GrantAmount, Publications
# N:M relationships between Person and other entities
Q1_CRITERIA = [
    {
        "id": 1, "criterion": "Person entity identification",
        "description": "Correctly identifies Person as superclass with attributes SSN (PK), Name, Address.",
        "marks": 3,
    },
    {
        "id": 2, "criterion": "Instructor subclass mapping",
        "description": "Correctly maps Instructor subclass with attributes Rank and Salary, with appropriate FK to Person.",
        "marks": 4,
    },
    {
        "id": 3, "criterion": "Researcher subclass mapping",
        "description": "Correctly maps Researcher subclass with attributes GrantAmount and Publications, with appropriate FK to Person.",
        "marks": 4,
    },
    {
        "id": 4, "criterion": "Superclass/subclass strategy",
        "description": "Uses appropriate mapping strategy for superclass/subclass (single relation, multiple relations, or shared PK).",
        "marks": 4,
    },
    {
        "id": 5, "criterion": "Correct ER notation",
        "description": "Entities use rectangles, attributes use ellipses, relationships use correct notation, PK underlined.",
        "marks": 3,
    },
    {
        "id": 6, "criterion": "Correct connections and keys",
        "description": "All attributes connected to correct entities, PKs clearly indicated, FKs reference correct relations.",
        "marks": 2,
    },
]

# ── Q1 Detection patterns per student (varying quality) ──────────────────
# label: "Entities" | "Attributes" | "Relationships" | "Subclass"
Q1_DETECTION_PROFILES = {
    "IT22262551": {  # 1st - Top: all entities, all attributes, perfect
        "entity_count": 3, "relationship_count": 2, "label_count": 12,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [50, 50, 200, 150], "confidence": 0.97, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [220, 30, 350, 80], "confidence": 0.96, "text": "SSN"},
            {"id": "2", "label": "Attributes", "bbox": [220, 90, 350, 140], "confidence": 0.95, "text": "Name"},
            {"id": "3", "label": "Attributes", "bbox": [220, 150, 350, 200], "confidence": 0.94, "text": "Address"},
            {"id": "4", "label": "Subclass", "bbox": [50, 250, 200, 350], "confidence": 0.96, "text": "Instructor"},
            {"id": "5", "label": "Attributes", "bbox": [220, 250, 350, 300], "confidence": 0.94, "text": "Rank"},
            {"id": "6", "label": "Attributes", "bbox": [220, 310, 350, 360], "confidence": 0.93, "text": "Salary"},
            {"id": "7", "label": "Subclass", "bbox": [50, 450, 200, 550], "confidence": 0.95, "text": "Researcher"},
            {"id": "8", "label": "Attributes", "bbox": [220, 450, 350, 500], "confidence": 0.93, "text": "GrantAmount"},
            {"id": "9", "label": "Attributes", "bbox": [220, 510, 350, 560], "confidence": 0.92, "text": "Publications"},
            {"id": "10", "label": "Relationships", "bbox": [400, 200, 550, 300], "confidence": 0.91, "text": "N"},
            {"id": "11", "label": "Relationships", "bbox": [400, 400, 550, 500], "confidence": 0.90, "text": "M"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN", "Name", "Address"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": ["GrantAmount", "Publications"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
            {"relation_name": "M", "entities": ["Person", "Researcher"], "attributes": []},
        ],
    },
    "IT22262552": {  # 2nd - Excellent: all entities, most attributes, minor strategy issue
        "entity_count": 3, "relationship_count": 2, "label_count": 11,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [60, 60, 210, 160], "confidence": 0.96, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [230, 40, 360, 90], "confidence": 0.95, "text": "SSN"},
            {"id": "2", "label": "Attributes", "bbox": [230, 100, 360, 150], "confidence": 0.94, "text": "Name"},
            {"id": "3", "label": "Attributes", "bbox": [230, 160, 360, 210], "confidence": 0.93, "text": "Address"},
            {"id": "4", "label": "Subclass", "bbox": [60, 260, 210, 360], "confidence": 0.95, "text": "Instructor"},
            {"id": "5", "label": "Attributes", "bbox": [230, 260, 360, 310], "confidence": 0.93, "text": "Rank"},
            {"id": "6", "label": "Attributes", "bbox": [230, 320, 360, 370], "confidence": 0.92, "text": "Salary"},
            {"id": "7", "label": "Subclass", "bbox": [60, 460, 210, 560], "confidence": 0.94, "text": "Researcher"},
            {"id": "8", "label": "Attributes", "bbox": [230, 460, 360, 510], "confidence": 0.92, "text": "GrantAmount"},
            {"id": "9", "label": "Attributes", "bbox": [230, 520, 360, 570], "confidence": 0.91, "text": "Publications"},
            {"id": "10", "label": "Relationships", "bbox": [410, 210, 560, 310], "confidence": 0.90, "text": "N"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN", "Name", "Address"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": ["GrantAmount", "Publications"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
            {"relation_name": "M", "entities": ["Person", "Researcher"], "attributes": []},
        ],
    },
    "IT22262553": {  # 3rd - Good: all entities, most attributes, minor notation issues
        "entity_count": 3, "relationship_count": 2, "label_count": 10,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [70, 70, 220, 170], "confidence": 0.95, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [240, 50, 370, 100], "confidence": 0.94, "text": "SSN"},
            {"id": "2", "label": "Attributes", "bbox": [240, 110, 370, 160], "confidence": 0.93, "text": "Name"},
            {"id": "3", "label": "Attributes", "bbox": [240, 170, 370, 220], "confidence": 0.92, "text": "Address"},
            {"id": "4", "label": "Subclass", "bbox": [70, 270, 220, 370], "confidence": 0.94, "text": "Instructor"},
            {"id": "5", "label": "Attributes", "bbox": [240, 270, 370, 320], "confidence": 0.92, "text": "Rank"},
            {"id": "6", "label": "Attributes", "bbox": [240, 330, 370, 380], "confidence": 0.91, "text": "Salary"},
            {"id": "7", "label": "Subclass", "bbox": [70, 470, 220, 570], "confidence": 0.93, "text": "Researcher"},
            {"id": "8", "label": "Attributes", "bbox": [240, 470, 370, 520], "confidence": 0.91, "text": "GrantAmount"},
            {"id": "9", "label": "Relationships", "bbox": [420, 220, 570, 320], "confidence": 0.90, "text": "N"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN", "Name", "Address"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": ["GrantAmount"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
            {"relation_name": "M", "entities": ["Person", "Researcher"], "attributes": []},
        ],
    },
    "IT22262554": {  # 4th - Good: all entities, missing Address
        "entity_count": 3, "relationship_count": 2, "label_count": 9,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [80, 80, 230, 180], "confidence": 0.94, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [250, 60, 380, 110], "confidence": 0.93, "text": "SSN"},
            {"id": "2", "label": "Attributes", "bbox": [250, 120, 380, 170], "confidence": 0.92, "text": "Name"},
            {"id": "3", "label": "Subclass", "bbox": [80, 280, 230, 380], "confidence": 0.93, "text": "Instructor"},
            {"id": "4", "label": "Attributes", "bbox": [250, 280, 380, 330], "confidence": 0.91, "text": "Rank"},
            {"id": "5", "label": "Attributes", "bbox": [250, 340, 380, 390], "confidence": 0.90, "text": "Salary"},
            {"id": "6", "label": "Subclass", "bbox": [80, 480, 230, 580], "confidence": 0.92, "text": "Researcher"},
            {"id": "7", "label": "Attributes", "bbox": [250, 480, 380, 530], "confidence": 0.90, "text": "GrantAmount"},
            {"id": "8", "label": "Relationships", "bbox": [430, 230, 580, 330], "confidence": 0.89, "text": "N"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN", "Name"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": ["GrantAmount"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
            {"relation_name": "M", "entities": ["Person", "Researcher"], "attributes": []},
        ],
    },
    "IT22262555": {  # 5th - Average: Person missing Name, Researcher missing attrs
        "entity_count": 3, "relationship_count": 2, "label_count": 8,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [90, 90, 240, 190], "confidence": 0.93, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [260, 70, 390, 120], "confidence": 0.92, "text": "SSN"},
            {"id": "2", "label": "Subclass", "bbox": [90, 290, 240, 390], "confidence": 0.92, "text": "Instructor"},
            {"id": "3", "label": "Attributes", "bbox": [260, 290, 390, 340], "confidence": 0.91, "text": "Rank"},
            {"id": "4", "label": "Attributes", "bbox": [260, 350, 390, 400], "confidence": 0.90, "text": "Salary"},
            {"id": "5", "label": "Subclass", "bbox": [90, 490, 240, 590], "confidence": 0.91, "text": "Researcher"},
            {"id": "6", "label": "Relationships", "bbox": [440, 240, 590, 340], "confidence": 0.89, "text": "N"},
            {"id": "7", "label": "Relationships", "bbox": [440, 440, 590, 540], "confidence": 0.88, "text": "M"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": []},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
            {"relation_name": "M", "entities": ["Person", "Researcher"], "attributes": []},
        ],
    },
    "IT22262556": {  # 6th - Below Avg: Person missing Name/Address, Researcher attrs missing
        "entity_count": 3, "relationship_count": 1, "label_count": 7,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [100, 100, 250, 200], "confidence": 0.92, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [270, 80, 400, 130], "confidence": 0.91, "text": "SSN"},
            {"id": "2", "label": "Subclass", "bbox": [100, 300, 250, 400], "confidence": 0.91, "text": "Instructor"},
            {"id": "3", "label": "Attributes", "bbox": [270, 300, 400, 350], "confidence": 0.90, "text": "Rank"},
            {"id": "4", "label": "Attributes", "bbox": [270, 360, 400, 410], "confidence": 0.89, "text": "Salary"},
            {"id": "5", "label": "Subclass", "bbox": [100, 500, 250, 600], "confidence": 0.90, "text": "Researcher"},
            {"id": "6", "label": "Relationships", "bbox": [450, 250, 600, 350], "confidence": 0.88, "text": "N"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN"]},
            {"entity_name": "Instructor", "attributes": ["Rank", "Salary"]},
            {"entity_name": "Researcher", "attributes": []},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
        ],
    },
    "IT22262557": {  # 7th - Weak: Person SSN only, Instructor missing Salary, no Researcher
        "entity_count": 2, "relationship_count": 1, "label_count": 5,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [110, 110, 260, 210], "confidence": 0.91, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [280, 90, 410, 140], "confidence": 0.90, "text": "SSN"},
            {"id": "2", "label": "Subclass", "bbox": [110, 310, 260, 410], "confidence": 0.90, "text": "Instructor"},
            {"id": "3", "label": "Attributes", "bbox": [280, 310, 410, 360], "confidence": 0.89, "text": "Rank"},
            {"id": "4", "label": "Relationships", "bbox": [460, 260, 610, 360], "confidence": 0.87, "text": "N"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN"]},
            {"entity_name": "Instructor", "attributes": ["Rank"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
        ],
    },
    "IT22262558": {  # 8th - Poor: Person SSN+Name, Instructor Rank only, no Researcher
        "entity_count": 2, "relationship_count": 1, "label_count": 4,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [120, 120, 270, 220], "confidence": 0.90, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [290, 100, 420, 150], "confidence": 0.89, "text": "SSN"},
            {"id": "2", "label": "Subclass", "bbox": [120, 320, 270, 420], "confidence": 0.89, "text": "Instructor"},
            {"id": "3", "label": "Attributes", "bbox": [290, 320, 420, 370], "confidence": 0.88, "text": "Rank"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN", "Name"]},
            {"entity_name": "Instructor", "attributes": ["Rank"]},
        ],
        "relationships": [
            {"relation_name": "N", "entities": ["Person", "Instructor"], "attributes": []},
        ],
    },
    "IT22262559": {  # 9th - Very Poor: Person SSN only, Instructor Rank only
        "entity_count": 2, "relationship_count": 0, "label_count": 3,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [130, 130, 280, 230], "confidence": 0.89, "text": "Person"},
            {"id": "1", "label": "Attributes", "bbox": [300, 110, 430, 160], "confidence": 0.88, "text": "SSN"},
            {"id": "2", "label": "Subclass", "bbox": [130, 330, 280, 430], "confidence": 0.88, "text": "Instructor"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": ["SSN"]},
            {"entity_name": "Instructor", "attributes": ["Rank"]},
        ],
        "relationships": [],
    },
    "IT22262560": {  # 10th - Failing: only Person entity, no attributes drawn
        "entity_count": 1, "relationship_count": 0, "label_count": 1,
        "detections": [
            {"id": "0", "label": "Entities", "bbox": [140, 140, 290, 240], "confidence": 0.87, "text": "Person"},
        ],
        "entities": [
            {"entity_name": "Person", "attributes": []},
        ],
        "relationships": [],
    },
}

# ── Q1 Evaluation scores per student ─────────────────────────────────────
# Maps to criteria: [Person id(3), Instructor map(4), Researcher map(4), Strategy(4), Notation(3), Connections(2)]
Q1_SCORES = {
    "IT22262551": [3, 4, 4, 4, 3, 2],  # 20/20  Top
    "IT22262552": [3, 4, 4, 3, 3, 2],  # 19/20  Excellent
    "IT22262553": [3, 3, 3, 3, 3, 2],  # 17/20  Good
    "IT22262554": [2, 3, 3, 3, 2, 2],  # 15/20  Good
    "IT22262555": [2, 3, 2, 2, 2, 2],  # 13/20  Average
    "IT22262556": [2, 2, 2, 2, 2, 1],  # 11/20  Below Avg
    "IT22262557": [1, 2, 2, 2, 1, 1],  # 9/20   Weak
    "IT22262558": [1, 2, 1, 1, 1, 1],  # 7/20   Poor
    "IT22262559": [1, 1, 1, 1, 1, 0],  # 5/20   Very Poor
    "IT22262560": [0, 1, 0, 0, 1, 0],  # 2/20   Failing
}

Q1_FEEDBACK = {
    "IT22262551": "Outstanding EER diagram. All entities, attributes, relationships and notation perfectly represented. Complete superclass/subclass mapping with correct FK references.",
    "IT22262552": "Excellent diagram with all three entities and most attributes correct. Minor issue with superclass/subclass strategy clarity.",
    "IT22262553": "Good diagram. Person and Instructor correctly mapped. Researcher missing Publications attribute. Strategy is correct but notation has minor issues.",
    "IT22262554": "Good diagram with all entities present. Missing Address attribute on Person. Connections mostly correct.",
    "IT22262555": "Average diagram. Person missing Name. Researcher missing GrantAmount and Publications. Basic structure correct.",
    "IT22262556": "Below average. Missing Person Name/Address and Researcher attributes. Only basic entity rectangles drawn.",
    "IT22262557": "Weak diagram. Person has only SSN. Instructor missing Salary. Researcher entirely absent. Limited ER notation.",
    "IT22262558": "Poor diagram. Missing most attributes on Person. Researcher absent. Instructor has no attributes. Minimal connections.",
    "IT22262559": "Very poor. Only Person with SSN and Instructor with Rank identified. All other attributes and Researcher missing.",
    "IT22262560": "Failing. Only Person entity identified. No attributes, no subclasses, no relationships drawn correctly.",
}

# ── Q2-Q4 Theory Submissions ─────────────────────────────────────────────
# Each student's raw OCR transcript for Q2, Q3, Q4

def make_transcript(student_id: str, variant: int) -> str:
    """Generate a realistic OCR transcript for theory questions Q2-Q4."""
    transcripts = {
        0: f"""Student ID: {student_id}

Question 2
a) Given FDs: A→BC, BC→E, E→DA

A⁺: Start with {{A}}. A→BC adds {{B,C}}. BC→E adds {{E}}. E→DA adds {{D,A}}. So A⁺ = {{A,B,C,D,E}} = R. A is a candidate key.

BC⁺: Start with {{B,C}}. BC→E adds {{E}}. E→DA adds {{D,A}}. Now we have {{A,B,C,D,E}} = R. BC is a candidate key.

CD⁺: Start with {{C,D}}. No FD starts with C alone or D alone or CD. CD⁺ = {{C,D}}. Not a superkey.

BE⁺: Start with {{B,E}}. BC→E is satisfied. E→DA adds {{D,A}}. Now {{A,B,D,E}}. A→BC adds {{C}}. BE⁺ = {{A,B,C,D,E}} = R. BE is a candidate key.

Candidate keys: A, BC, BE.

b) Is R in 3NF?
For 3NF, for every non-trivial FD X→Y, either X is a superkey or Y is a prime attribute.
A→BC: A is superkey ✓
BC→E: BC is superkey ✓
E→DA: E is not a superkey. D and A are prime (part of keys A and BE). So DA contains prime attributes. ✓
R is in 3NF.

c) Is R in BCNF?
For BCNF, every determinant must be a superkey.
E→DA: E is not a superkey (E⁺ = {{A,D,E}} ≠ R). So R is NOT in BCNF.

BCNF decomposition:
R1(E, D, A) with FD E→DA, E is PK
R2(A, B, C) with FD A→BC, A is PK
R3(B, C, E) with FD BC→E, BC is PK

Question 3
a) π_ename, salary(DEPT ⨝ mgrEno=eNo EMP)

b) π_iname, price, availableQty(ITEM) \\ π_iname, price, availableQty(ITEM ⨝ itemNo=itemNo SALES)

c) (π_ename(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM))) ∩ (π_ename(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM)))

d) π_iname(ITEM ⨝ SALES) grouped by iname with γ_sum(soldQty) > 1000

e) π_iname(ITEM ⨝ SALES) grouped by iname, ordered by sum(soldQty) DESC, LIMIT 1

Question 4
a) i) SELECT c.name, c.phone FROM Customers c, Orders o, OrderDetails od, Products p WHERE c.cid = o.cid AND o.oid = od.oid AND od.productId = p.productId AND p.UnitPrice > 500;

ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (SELECT od.productId FROM OrderDetails od, Orders o, Customers c WHERE od.oid = o.oid AND o.cid = c.cid AND c.country = 'Germany');

iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (SELECT o.cid FROM Orders o, OrderDetails od WHERE o.oid = od.oid AND od.discount <= 0.05);

b) CREATE VIEW incompleteOrders AS
SELECT c.name, c.country, COUNT(DISTINCT o.oid) AS incomplete_count
FROM Customers c
JOIN Orders o ON c.cid = o.cid
JOIN OrderDetails od ON o.oid = od.oid
JOIN Products p ON od.productId = p.productId
WHERE p.unitsInStock < od.quantity
GROUP BY c.name, c.country;

c) CREATE FUNCTION calc_lost(order_id INT, discount REAL)
RETURNS REAL AS $$
DECLARE
    total_cost REAL := 0;
    rec RECORD;
BEGIN
    FOR rec IN SELECT od.quantity, p.UnitPrice
               FROM OrderDetails od JOIN Products p ON od.productId = p.productId
               WHERE od.oid = order_id
    LOOP
        total_cost := total_cost + (rec.UnitPrice * rec.quantity);
    END LOOP;
    RETURN total_cost * (1 - discount);
END;
$$ LANGUAGE plpgsql;

d) CREATE TRIGGER updateCost
AFTER INSERT ON OrderDetails
FOR EACH ROW
BEGIN
    UPDATE Orders
    SET cost = calc_lost(NEW.oid, (SELECT discount FROM OrderDetails WHERE oid = NEW.oid))
    WHERE oid = NEW.oid;
END;""",

        1: f"""Student ID: {student_id}

Question 2
a) FDs: A→BC, BC→E, E→DA

A⁺: {{A}} → {{A,B,C}} → {{A,B,C,E}} → {{A,B,C,D,E}} = R. A is key.
BC⁺: {{B,C}} → {{B,C,E}} → {{A,B,C,D,E}} = R. BC is key.
BE⁺: {{B,E}} → {{A,B,D,E}} → {{A,B,C,D,E}} = R. BE is key.

Candidate keys: {{A}}, {{BC}}, {{BE}}

b) 3NF check:
A→BC: A is superkey ✓
BC→E: BC is superkey ✓
E→DA: E is not superkey, but DA contains prime attributes (A is prime) ✓
R is in 3NF.

c) BCNF check:
E→DA: E is not superkey (E⁺ = {{A,D,E}}) → NOT in BCNF

BCNF decomposition:
R1(A, B, C) - FD: A→BC
R2(B, C, E) - FD: BC→E
R3(E, D, A) - FD: E→DA

Question 3
a) π_eName, salary(DEPT ⨝ mgrEno=eNo EMP)

b) π_itemName, price, availableQty(ITEM) \\ π_itemName, price, availableQty(ITEM ⨝ itemNo=itemNo SALES)

c) (π_eName(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM))) ∩ (π_eName(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM)))

d) π_itemName(ITEM ⨝ SALES) grouped by itemName with γ_sum(soldQty) > 1000

e) π_itemName(ITEM ⨝ SALES) grouped by itemName, ordered by sum(soldQty) DESC, LIMIT 1

Question 4
a) i) SELECT c.name, c.phone FROM Customers c, Orders o, OrderDetails od, Products p WHERE c.cid = o.cid AND o.oid = od.oid AND od.productId = p.productId AND p.UnitPrice > 500;

ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (SELECT od.productId FROM OrderDetails od, Orders o, Customers c WHERE od.oid = o.oid AND o.cid = c.cid AND c.country = 'Germany');

iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (SELECT o.cid FROM Orders o, OrderDetails od WHERE o.oid = od.oid AND od.discount <= 0.05);

b) CREATE VIEW incompleteOrders AS
SELECT c.name, c.country, COUNT(DISTINCT o.oid) AS incomplete_count
FROM Customers c
JOIN Orders o ON c.cid = o.cid
JOIN OrderDetails od ON o.oid = od.oid
JOIN Products p ON od.productId = p.productId
WHERE p.unitsInStock < od.quantity
GROUP BY c.name, c.country;

c) CREATE FUNCTION calc_lost(order_id INT, discount REAL)
RETURNS REAL AS $$
DECLARE total REAL := 0;
BEGIN
    SELECT SUM(p.UnitPrice * od.quantity) INTO total
    FROM OrderDetails od JOIN Products p ON od.productId = p.productId
    WHERE od.oid = order_id;
    RETURN total * (1 - discount);
END;
$$ LANGUAGE plpgsql;

d) CREATE TRIGGER updateCost
AFTER INSERT ON OrderDetails
FOR EACH ROW
BEGIN
    UPDATE Orders SET cost = calc_lost(NEW.oid, 0) WHERE oid = NEW.oid;
END;""",

        2: f"""Student ID: {student_id}

Question 2
a) FDs: A→BC, BC→E, E→DA

Finding keys:
A⁺ = {{A,B,C,D,E}} = R → A is key
BC⁺ = {{A,B,C,D,E}} = R → BC is key
BE⁺ = {{A,B,C,D,E}} = R → BE is key

Candidate keys: A, BC, BE

b) R is in 3NF because for every FD X→Y, either X is superkey or Y is prime.

c) R is NOT in BCNF because E→DA violates BCNF (E is not superkey).
Decomposition: R1(E,D,A), R2(A,B,C), R3(B,C,E)

Question 3
a) π_eName,salary(DEPT ⨝ mgrEno=eNo EMP)

b) Items not sold:
π_iname,price,availableQty(ITEM) \\ π_iname,price,availableQty(ITEM ⨝ itemNo=itemNo SALES)

c) Employees who sold both:
π_eName(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM)) ∩ π_eName(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM))

d) Items with >1000 sold:
π_iname(ITEM ⨝ SALES) grouped by iname with sum(soldQty) > 1000

e) Most sold item:
π_iname(ITEM ⨝ SALES) grouped by iname, ordered by sum(soldQty) DESC, LIMIT 1

Question 4
a) i) SELECT c.name, c.phone FROM Customers c JOIN Orders o ON c.cid = o.cid JOIN OrderDetails od ON o.oid = od.oid JOIN Products p ON od.productId = p.productId WHERE p.UnitPrice > 500;

ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (SELECT od.productId FROM OrderDetails od JOIN Orders o ON od.oid = o.oid JOIN Customers c ON o.cid = c.cid WHERE c.country = 'Germany');

iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (SELECT o.cid FROM Orders o JOIN OrderDetails od ON o.oid = od.oid WHERE od.discount <= 0.05);

b) CREATE VIEW incompleteOrders AS SELECT c.name, c.country, COUNT(o.oid) as times_not_completed FROM Customers c JOIN Orders o ON c.cid = o.cid WHERE EXISTS (SELECT 1 FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = o.oid AND p.unitsInStock < od.quantity) GROUP BY c.name, c.country;

c) CREATE FUNCTION calc_lost(order_id INT, discount REAL) RETURNS REAL AS $$ DECLARE total REAL; BEGIN SELECT SUM(p.UnitPrice * od.quantity) INTO total FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = order_id; RETURN total * (1 - discount); END; $$ LANGUAGE plpgsql;

d) CREATE TRIGGER updateCost AFTER INSERT ON OrderDetails FOR EACH ROW EXECUTE FUNCTION calc_lost(NEW.oid, (SELECT discount FROM OrderDetails WHERE oid = NEW.oid LIMIT 1));""",

        3: f"""Student ID: {student_id}

Question 2
a) Given FDs: A→BC, BC→E, E→DA

A⁺ = {{A,B,C,D,E}} = R (A is key)
BC⁺ = {{A,B,C,D,E}} = R (BC is key)
BE⁺ = {{A,B,C,D,E}} = R (BE is key)

Candidate keys: A, BC, BE

b) R is in 3NF. Every non-trivial FD has a superkey on left side or prime attributes on right side.

c) R is NOT in BCNF because E→DA where E is not a superkey.
Decompose into: R1(E,D,A), R2(A,B,C), R3(B,C,E)

Question 3
a) π_eName,salary(DEPT ⨝ mgrEno=eNo EMP)

b) π_iname,price,availableQty(ITEM) - π_iname,price,availableQty(ITEM ⨝ itemNo=itemNo SALES)

c) π_eName(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM)) ∩ π_eName(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM))

d) π_iname(ITEM ⨝ SALES) grouped by iname with γ_sum(soldQty) > 1000

e) π_iname(ITEM ⨝ SALES) grouped by iname ORDER BY sum(soldQty) DESC LIMIT 1

Question 4
a) i) SELECT c.name, c.phone FROM Customers c JOIN Orders o ON c.cid = o.cid JOIN OrderDetails od ON o.oid = od.oid JOIN Products p ON od.productId = p.productId WHERE p.UnitPrice > 500;

ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (SELECT od.productId FROM OrderDetails od JOIN Orders o ON od.oid = o.oid JOIN Customers c ON o.cid = c.cid WHERE c.country = 'Germany');

iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (SELECT o.cid FROM Orders o JOIN OrderDetails od ON o.oid = od.oid WHERE od.discount <= 0.05);

b) CREATE VIEW incompleteOrders AS SELECT c.name, c.country, COUNT(o.oid) as not_completed FROM Customers c JOIN Orders o ON c.cid = o.cid WHERE EXISTS (SELECT 1 FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = o.oid AND p.unitsInStock < od.quantity) GROUP BY c.name, c.country;

c) CREATE FUNCTION calc_lost(order_id INT, discount REAL) RETURNS REAL AS $$ DECLARE total REAL := 0; BEGIN SELECT SUM(p.UnitPrice * od.quantity) INTO total FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = order_id; RETURN total * (1 - discount); END; $$ LANGUAGE plpgsql;

d) CREATE TRIGGER updateCost AFTER INSERT ON OrderDetails FOR EACH ROW BEGIN UPDATE Orders SET cost = calc_lost(NEW.oid, (SELECT discount FROM OrderDetails WHERE oid = NEW.oid)) WHERE oid = NEW.oid; END;""",

        4: f"""Student ID: {student_id}

Question 2
a) FDs: A→BC, BC→E, E→DA

A⁺ = {{A,B,C,D,E}} = R → A is key
BC⁺ = {{A,B,C,D,E}} = R → BC is key
BE⁺ = {{A,B,C,D,E}} = R → BE is key

b) R is in 3NF. For E→DA, E is not superkey but D,A are prime attributes.

c) R is NOT in BCNF. E→DA violates BCNF. Decompose: R1(E,D,A), R2(A,B,C), R3(B,C,E)

Question 3
a) π_eName, salary(DEPT ⨝ mgrEno=eNo EMP)

b) π_iname, price, availableQty(ITEM) \\ π_iname, price, availableQty(ITEM ⨝ itemNo=itemNo SALES)

c) π_eName(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM)) ∩ π_eName(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM))

d) π_iname(ITEM ⨝ SALES) grouped by iname with sum(soldQty) > 1000

e) π_iname(ITEM ⨝ SALES) grouped by iname ORDER BY sum(soldQty) DESC LIMIT 1

Question 4
a) i) SELECT c.name, c.phone FROM Customers c JOIN Orders o ON c.cid = o.cid JOIN OrderDetails od ON o.oid = od.oid JOIN Products p ON od.productId = p.productId WHERE p.UnitPrice > 500;

ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (SELECT od.productId FROM OrderDetails od JOIN Orders o ON od.oid = o.oid JOIN Customers c ON o.cid = c.cid WHERE c.country = 'Germany');

iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (SELECT o.cid FROM Orders o JOIN OrderDetails od ON o.oid = od.oid WHERE od.discount <= 0.05);

b) CREATE VIEW incompleteOrders AS SELECT c.name, c.country, COUNT(o.oid) as not_completed FROM Customers c JOIN Orders o ON c.cid = o.cid WHERE EXISTS (SELECT 1 FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = o.oid AND p.unitsInStock < od.quantity) GROUP BY c.name, c.country;

c) CREATE FUNCTION calc_lost(order_id INT, discount REAL) RETURNS REAL AS $$ DECLARE total REAL; BEGIN SELECT SUM(p.UnitPrice * od.quantity) INTO total FROM OrderDetails od JOIN Products p ON od.productId = p.productId WHERE od.oid = order_id; RETURN total * (1 - discount); END; $$ LANGUAGE plpgsql;

d) CREATE TRIGGER updateCost AFTER INSERT ON OrderDetails FOR EACH ROW BEGIN UPDATE Orders SET cost = calc_lost(NEW.oid, 0) WHERE oid = NEW.oid; END;""",
    }
    return transcripts.get(variant % 5, transcripts[0])


# ── Theory evaluation scores per student ──────────────────────────────────
# Q2 (15 marks): [a:9, b:3, c:3]
# Q3 (25 marks): [a:2, b:4, c:5, d:6, e:8]
# Q4 (40 marks): [a1:4, a2:5, a3:6, b:7, c:8, d:10]
THEORY_SCORES = {
    "IT22262551": {"q2": [9, 3, 3], "q3": [2, 4, 5, 6, 8], "q4": [4, 5, 6, 7, 8, 10]},  # 80/80  Top
    "IT22262552": {"q2": [8, 3, 3], "q3": [2, 4, 5, 5, 7], "q4": [4, 5, 5, 6, 8, 9]},  # 74/80  Excellent
    "IT22262553": {"q2": [7, 2, 2], "q3": [2, 3, 4, 5, 6], "q4": [3, 4, 5, 6, 7, 8]},  # 65/80  Good
    "IT22262554": {"q2": [6, 2, 2], "q3": [2, 3, 4, 4, 6], "q4": [3, 4, 4, 5, 6, 8]},  # 59/80  Good
    "IT22262555": {"q2": [5, 2, 2], "q3": [1, 2, 3, 4, 5], "q4": [2, 3, 4, 5, 5, 7]},  # 49/80  Average
    "IT22262556": {"q2": [4, 1, 1], "q3": [1, 2, 2, 3, 4], "q4": [2, 2, 3, 4, 5, 6]},  # 40/80  Below Avg
    "IT22262557": {"q2": [3, 1, 1], "q3": [1, 1, 2, 3, 3], "q4": [1, 2, 2, 3, 4, 5]},  # 29/80  Weak
    "IT22262558": {"q2": [3, 1, 0], "q3": [1, 1, 2, 2, 3], "q4": [1, 1, 2, 3, 3, 4]},  # 24/80  Poor
    "IT22262559": {"q2": [2, 0, 0], "q3": [0, 1, 1, 2, 2], "q4": [1, 1, 1, 2, 2, 3]},  # 16/80  Very Poor
    "IT22262560": {"q2": [1, 0, 0], "q3": [0, 0, 1, 1, 1], "q4": [0, 1, 1, 1, 1, 2]},  # 9/80   Failing
}

# ── Build rubricCollection ────────────────────────────────────────────────
RUBRIC_THEORY = {
    "subject_code": SUBJECT_CODE,
    "subject_name": SUBJECT_NAME,
    "year": YEAR,
    "month": MONTH,
    "semester": SEMESTER,
    "session_name": SESSION_NAME,
    "filename": "IT2040_2024_final_exam.pdf",
    "parsed_at": 1720000000.124,
    "exam_roster": STUDENT_IDS,
    "questions": [
        {
            "question_no": "02",
            "question_text": "Consider a relation R(A,B,C,D,E), with the following set of functional dependencies over R: F={A→BC, BC→E, E→DA}.\na) Find all the keys that follow from the given FDs using Armstrong's axioms, showing how you found them. (9 marks)\nb) Is R in 3NF? Give reasons for your conclusion. (3 marks)\nc) Is R in BCNF? Give reasons for your conclusion. If R is not in BCNF, convert it to a set of BCNF relations. (3 marks)",
            "max_marks": 15,
            "criteria": [
                {"point": "Correctly computes attribute closures to find candidate keys", "marks": 3},
                {"point": "Identifies all candidate keys (A, BC, BE)", "marks": 3},
                {"point": "Shows step-by-step closure computation", "marks": 3},
                {"point": "Correctly determines 3NF with reasoning", "marks": 3},
                {"point": "Correctly determines BCNF violation and decomposes", "marks": 3},
            ],
            "model_answer": "Candidate keys: A, BC, BE. R is in 3NF (E→DA has prime RHS). R is not in BCNF (E→DA violates). BCNF decomposition: R1(E,D,A), R2(A,B,C), R3(B,C,E).",
        },
        {
            "question_no": "03",
            "question_text": "Consider the database of a department store that includes the following tables:\nITEM(ino, iname, dept, price, availableQty, cost)\nEMP(eno, ename, salary, comm, dept)\nDEPT(dno, dname, mgrEno)\nSALES(ido, eNo, soldTime, soldQty, soldPrice)\n\nWrite relational algebra statements to answer the following queries:\na) Display the name and salary of all managers. (2 marks)\nb) Display the names, prices and quantities available of items that are not sold. (4 marks)\nc) Display the names of employees who had sold both computers and cameras. (5 marks)\nd) Display the names of items which has more than 1000 pieces sold. (6 marks)\ne) Display the name of the items which are sold the most. (8 marks)",
            "max_marks": 25,
            "criteria": [
                {"point": "Correct relational algebra for manager names/salary", "marks": 2},
                {"point": "Correct set difference for unsold items", "marks": 4},
                {"point": "Correct intersection for employees selling both", "marks": 5},
                {"point": "Correct aggregation/grouping for items >1000 sold", "marks": 6},
                {"point": "Correct ordering and limiting for most sold item", "marks": 8},
            ],
            "model_answer": "a) π_ename,salary(DEPT ⨝ mgrEno=eNo EMP) b) π_iname,price,availableQty(ITEM) \\ π_iname,price,availableQty(ITEM ⨝ itemNo=itemNo SALES) c) π_eName(EMP ⨝ SALES ⨝ σ_itemName='computer'(ITEM)) ∩ π_eName(EMP ⨝ SALES ⨝ σ_itemName='camera'(ITEM)) d) π_iname(ITEM ⨝ SALES) grouped with γ_sum(soldQty)>1000 e) π_iname(ITEM ⨝ SALES) grouped, ordered by sum(soldQty) DESC, LIMIT 1",
        },
        {
            "question_no": "04",
            "question_text": "Consider the following relations in a database created for an online store:\nCustomers(cid, name, phone, country)\nEmployees(eid, ename, phone, hiredate)\nOrders(oid, eid, cid, orderDate, requiredDate, shippedDate)\nOrderDetails(oid, productId, quantity, discount)\nProducts(productId, productName, UnitPrice, unitsInStock, ROL)\n\na) Use SQL queries to answer following questions.\ni. Display the name and address of customers who had ordered products which cost over Rs.500. (4 marks)\nii. Find the names and unit prices of all products which has not been ordered by customers from 'Germany'. (5 marks)\niii. Find the customer ids and names of the customers who have obtained more than 5% discount for every product in every order they have placed. (6 marks)\nb) Create a view named incompleteOrders that contains customer name, country and number of times an order is not completed. (7 marks)\nc) Create a function named calc_lost to calculate and return the total cost of an order given the order id and the discount. (8 marks)\nd) Create a trigger named updateCost to update the cost column when order details are added. (10 marks)",
            "max_marks": 40,
            "criteria": [
                {"point": "Correct SQL for customers ordering products >500", "marks": 4},
                {"point": "Correct SQL for products not ordered by German customers", "marks": 5},
                {"point": "Correct SQL for customers with >5% discount on all products", "marks": 6},
                {"point": "Correct VIEW creation with proper JOIN and filtering", "marks": 7},
                {"point": "Correct FUNCTION with loop/aggregation and discount calc", "marks": 8},
                {"point": "Correct TRIGGER that updates cost using the function", "marks": 10},
            ],
            "model_answer": "a) i) SELECT c.name, c.phone FROM Customers c JOIN Orders o ON c.cid=o.cid JOIN OrderDetails od ON o.oid=od.oid JOIN Products p ON od.productId=p.productId WHERE p.UnitPrice>500; ii) SELECT p.productName, p.UnitPrice FROM Products p WHERE p.productId NOT IN (...German orders...); iii) SELECT c.cid, c.name FROM Customers c WHERE c.cid NOT IN (...discount<=0.05...); b) CREATE VIEW incompleteOrders AS ...; c) CREATE FUNCTION calc_lost ...; d) CREATE TRIGGER updateCost ...",
        },
    ],
}

# ── RUBRIC for Diagram Q1 (guideLines format for diagram evaluation) ─────
RUBRIC_DIAGRAM = {
    "examCode": EXAM_CODE,
    "subject_code": SUBJECT_CODE,
    "subject_name": SUBJECT_NAME,
    "year": YEAR,
    "month": MONTH,
    "semester": SEMESTER,
    "session_name": SESSION_NAME,
    "guideLines": [
        {
            "id": c["id"],
            "criterion": c["criterion"],
            "description": c["description"],
            "marks": c["marks"],
        }
        for c in Q1_CRITERIA
    ],
}


def build_diagram_evaluation(student_id: str) -> dict:
    scores = Q1_SCORES[student_id]
    total = sum(scores)
    max_total = sum(c["marks"] for c in Q1_CRITERIA)
    criteria_results = []
    for i, c in enumerate(Q1_CRITERIA):
        awarded = scores[i]
        max_m = c["marks"]
        if awarded == max_m:
            status = "pass"
        elif awarded >= max_m * 0.5:
            status = "partial"
        else:
            status = "fail"
        criteria_results.append({
            "criterion_id": c["id"],
            "criterion": c["criterion"],
            "awarded_marks": awarded,
            "max_marks": max_m,
            "status": status,
            "remarks": f"{'Fully' if status == 'pass' else 'Partially' if status == 'partial' else 'Not'} demonstrated",
        })
    now = datetime.now(timezone.utc).isoformat()
    return {
        "student_id": student_id,
        "subject_code": SUBJECT_CODE,
        "subject_name": SUBJECT_NAME,
        "year": YEAR,
        "month": MONTH,
        "semester": SEMESTER,
        "session_name": SESSION_NAME,
        "exam_code": EXAM_CODE,
        "rubric_ref": None,
        "evaluation_result": {
            "total_score": total,
            "max_score": max_total,
            "criteria_results": criteria_results,
            "overall_feedback": Q1_FEEDBACK[student_id],
            "grading_source": "colab",
        },
        "created_at": now,
        "updated_at": now,
    }


def build_diagram_marking(student_id: str) -> dict:
    profile = Q1_DETECTION_PROFILES[student_id]
    now = datetime.now(timezone.utc).isoformat()
    scores = Q1_SCORES[student_id]
    diagram_marks = sum(scores)
    return {
        "student_id": student_id,
        "subject_code": SUBJECT_CODE,
        "subject_name": SUBJECT_NAME,
        "year": YEAR,
        "month": MONTH,
        "semester": SEMESTER,
        "session_name": SESSION_NAME,
        "diagram_marks": diagram_marks,
        "diagram_details": {
            "label_count": profile["label_count"],
            "entity_count": profile["entity_count"],
            "relationship_count": profile["relationship_count"],
            "detections": profile["detections"],
            "entities": profile["entities"],
            "relationships": profile["relationships"],
            "structure": {
                "entities": {e["entity_name"]: {"attributes": e["attributes"]} for e in profile["entities"]},
                "relationships": profile["relationships"],
                "unmatched_connections": [],
            },
        },
        "diagram_entity_relations": profile["entities"],
        "diagram_relations": profile["relationships"],
        "remarks": "",
        "evaluation_result": {
            "status": "ok",
            "detections": [
                {**d, "crop_path": "", "ocr_status": "ok"}
                for d in profile["detections"]
            ],
            "connections": [],
            "structure": {
                "entities": {e["entity_name"]: {"attributes": e["attributes"]} for e in profile["entities"]},
                "relationships": profile["relationships"],
                "unmatched_connections": [],
            },
            "ocr": [],
            "save_dir": "",
        },
        "created_at": now,
        "updated_at": now,
        "source": "diagram-evaluation",
    }


def build_submission(student_id: str, variant: int) -> dict:
    tscores = THEORY_SCORES[student_id]
    q2_total = sum(tscores["q2"])
    q3_total = sum(tscores["q3"])
    q4_total = sum(tscores["q4"])
    theory_total = q2_total + q3_total + q4_total
    max_theory = 80  # Q2(15) + Q3(25) + Q4(40)

    transcript = make_transcript(student_id, variant)

    # Build per-question evaluation results
    evaluation_results = []
    q2_criteria = [
        {"criterion": "Attribute closures computation", "max_marks": 3, "awarded_marks": tscores["q2"][0] if tscores["q2"][0] <= 3 else 3, "achieved": tscores["q2"][0] >= 3},
        {"criterion": "Candidate key identification", "max_marks": 3, "awarded_marks": min(tscores["q2"][0], 3), "achieved": tscores["q2"][0] >= 6},
        {"criterion": "Step-by-step closure", "max_marks": 3, "awarded_marks": min(tscores["q2"][0] - 3, 3) if tscores["q2"][0] > 3 else 0, "achieved": tscores["q2"][0] >= 6},
        {"criterion": "3NF determination", "max_marks": 3, "awarded_marks": tscores["q2"][1], "achieved": tscores["q2"][1] >= 2},
        {"criterion": "BCNF decomposition", "max_marks": 3, "awarded_marks": tscores["q2"][2], "achieved": tscores["q2"][2] >= 2},
    ]
    evaluation_results.append({
        "question_no": "02",
        "score": q2_total,
        "max_score": 15,
        "criteria_performance": q2_criteria,
    })

    q3_criteria = [
        {"criterion": "Manager names/salary", "max_marks": 2, "awarded_marks": tscores["q3"][0], "achieved": tscores["q3"][0] >= 2},
        {"criterion": "Unsold items", "max_marks": 4, "awarded_marks": tscores["q3"][1], "achieved": tscores["q3"][1] >= 3},
        {"criterion": "Employees selling both", "max_marks": 5, "awarded_marks": tscores["q3"][2], "achieved": tscores["q3"][2] >= 4},
        {"criterion": "Items >1000 sold", "max_marks": 6, "awarded_marks": tscores["q3"][3], "achieved": tscores["q3"][3] >= 5},
        {"criterion": "Most sold item", "max_marks": 8, "awarded_marks": tscores["q3"][4], "achieved": tscores["q3"][4] >= 6},
    ]
    evaluation_results.append({
        "question_no": "03",
        "score": q3_total,
        "max_score": 25,
        "criteria_performance": q3_criteria,
    })

    q4_criteria = [
        {"criterion": "SQL query i", "max_marks": 4, "awarded_marks": tscores["q4"][0], "achieved": tscores["q4"][0] >= 3},
        {"criterion": "SQL query ii", "max_marks": 5, "awarded_marks": tscores["q4"][1], "achieved": tscores["q4"][1] >= 4},
        {"criterion": "SQL query iii", "max_marks": 6, "awarded_marks": tscores["q4"][2], "achieved": tscores["q4"][2] >= 5},
        {"criterion": "VIEW creation", "max_marks": 7, "awarded_marks": tscores["q4"][3], "achieved": tscores["q4"][3] >= 6},
        {"criterion": "FUNCTION creation", "max_marks": 8, "awarded_marks": tscores["q4"][4], "achieved": tscores["q4"][4] >= 6},
        {"criterion": "TRIGGER creation", "max_marks": 10, "awarded_marks": tscores["q4"][5], "achieved": tscores["q4"][5] >= 8},
    ]
    evaluation_results.append({
        "question_no": "04",
        "score": q4_total,
        "max_score": 40,
        "criteria_performance": q4_criteria,
    })

    now = datetime.now(timezone.utc).isoformat()
    return {
        "student_id": student_id,
        "rubric_ref": None,
        "paper_key": f"script_{STUDENT_IDS.index(student_id) + 1:02d}",
        "subject_code": SUBJECT_CODE,
        "subject_name": SUBJECT_NAME,
        "year": YEAR,
        "month": MONTH,
        "semester": SEMESTER,
        "session_name": SESSION_NAME,
        "max_marks_paper_total": 100.0,
        "max_marks_per_question": [
            {"question_no": "01", "max_marks": 20.0},
            {"question_no": "02", "max_marks": 15.0},
            {"question_no": "03", "max_marks": 25.0},
            {"question_no": "04", "max_marks": 40.0},
        ],
        "raw_ocr_transcript": transcript,
        "evaluation": {
            "total_score": theory_total,
            "max_score": max_theory,
            "results": evaluation_results,
        },
        "status": "graded",
        "processed_at": now,
        "created_at": now,
        "updated_at": now,
    }


def main():
    import pymongo

    client = pymongo.MongoClient("mongodb://127.0.0.1:27017")
    db = client["gradev2"]

    # ── rubricCollection ──────────────────────────────────────────────────
    db["rubricCollection"].delete_many({"subject_code": SUBJECT_CODE, "session_name": SESSION_NAME})
    db["rubricCollection"].insert_one(RUBRIC_THEORY)
    db["rubricCollection"].insert_one(RUBRIC_DIAGRAM)
    print(f"[OK] rubricCollection: 2 documents (theory Q2-Q4 + diagram Q1 guideLines)")

    # ── diagram_evaluation ────────────────────────────────────────────────
    db["diagram_evaluation"].delete_many({"subject_code": SUBJECT_CODE, "session_name": SESSION_NAME})
    evals = [build_diagram_evaluation(sid) for sid in STUDENT_IDS]
    db["diagram_evaluation"].insert_many(evals)
    print(f"[OK] diagram_evaluation: {len(evals)} documents")

    # ── diagram_marking ───────────────────────────────────────────────────
    db["diagram_marking"].delete_many({"subject_code": SUBJECT_CODE, "session_name": SESSION_NAME})
    marks = [build_diagram_marking(sid) for sid in STUDENT_IDS]
    db["diagram_marking"].insert_many(marks)
    print(f"[OK] diagram_marking: {len(marks)} documents")

    # ── submissions ───────────────────────────────────────────────────────
    db["submissions"].delete_many({"subject_code": SUBJECT_CODE, "session_name": SESSION_NAME})
    subs = [build_submission(sid, i) for i, sid in enumerate(STUDENT_IDS)]
    db["submissions"].insert_many(subs)
    print(f"[OK] submissions: {len(subs)} documents")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\nSummary of 'gradev2' database:")
    for name in sorted(db.list_collection_names()):
        count = db[name].count_documents({})
        print(f"  {name}: {count} documents")

    # ── Print score table ─────────────────────────────────────────────────
    print(f"\n{'Student':<15} {'Q1 Diagram':>10} {'Q2 Theory':>10} {'Q3 Theory':>10} {'Q4 Theory':>10} {'Total':>8}")
    print("-" * 70)
    for sid in STUDENT_IDS:
        d = sum(Q1_SCORES[sid])
        t = THEORY_SCORES[sid]
        q2 = sum(t["q2"])
        q3 = sum(t["q3"])
        q4 = sum(t["q4"])
        total = d + q2 + q3 + q4
        print(f"{sid:<15} {d:>10}/{20} {q2:>10}/{15} {q3:>10}/{25} {q4:>10}/{40} {total:>5}/{100}")

    client.close()


if __name__ == "__main__":
    main()
