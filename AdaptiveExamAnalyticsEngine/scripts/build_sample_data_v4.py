"""Build app/sample_data/sample_data_v4 from the IT2040 2022 Final Examination paper.

The 2022 paper is restructured so that it matches the sample_data_v3 shape:

* Original question 1 (EER model -> relational mapping) is REMOVED.
* Original question 2 (normalisation)          -> new question 01 (20 marks)
* Original question 3 (a-d: JDBC/backups/jobs) -> new question 02 (20 marks)
* Original question 3 (e: T-SQL school security) -> new question 03 (20 marks)
* Original question 4 (queries/function/trigger) -> new question 04 (20 marks)
* A NEW Create-level diagram question            -> new question 05 (20 marks)

Every question carries five rubric criteria worth four marks each, exactly like
sample_data_v3, so every downstream analytics module keeps working unchanged.

Fifty simulated Year-2 undergraduates write the scripts. Each student is given an
ability profile with per-topic skill biases, so the resulting papers look like real
scripts: correct fragments, partial fragments, common misconceptions, blank parts,
inconsistent formatting and the usual student noise.

Run from the repository root:
    python scripts/build_sample_data_v4.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "app" / "sample_data" / "sample_data_v4"

SEED = 20220601

SUBJECT_CODE = "IT2040"
SUBJECT_NAME = "Database Management Systems"
YEAR = 2022
MONTH = 6
SEMESTER = 1
SESSION_NAME = "Final Examination"
FILENAME = "IT2040 - 2022 Final Exam.pdf"
PARSED_AT = 1654041600.0
EXAM_CODE = "IT2040-2022-FINAL"

RUBRIC_OID = "6c1149ab7d0e5c1a3f2b8d40"
BASE_OID = "6c1149ab7d0e5c1a3f2b8d00"

CREATED_AT = "2026-09-05T09:30:00+05:30"
UPDATED_AT = "2026-09-05T11:45:00+05:30"
PROCESSED_AT = "2026-09-05T09:00:00+05:30"

STUDENT_IDS = [f"IT2123{n:04d}" for n in range(101, 151)]


# ─────────────────────────────────────────────────────────────────────────────
# 1. The paper
# ─────────────────────────────────────────────────────────────────────────────

QUESTIONS: list[dict] = [
    {
        "question_no": "01",
        "bloom_level": "Analyze",
        "max_marks": 20,
        "question_text": (
            "Consider relation R(A, B, C, D, E, F) with the set of functional dependencies "
            "F = {A -> CD, B -> E, F -> A}. (a) Find all the keys of R using the attribute "
            "closure method, showing each step of the closure. (b) Decide whether R is in 3NF "
            "and give reasons using the 3NF test. (c) Decide whether R is in BCNF and give "
            "reasons. If R is not in BCNF, decompose R into a set of BCNF relations, state the "
            "primary key of each new relation, and show that the decomposition is lossless and "
            "dependency preserving. (20 marks)"
        ),
        "criteria": [
            {"point": "Applies attribute closure to find every candidate key of R", "marks": 4},
            {"point": "Tests 3NF for every non-trivial dependency using prime attributes", "marks": 4},
            {"point": "Applies the BCNF test and identifies the violating dependencies", "marks": 4},
            {"point": "Derives a correct BCNF decomposition and states each primary key", "marks": 4},
            {"point": "Proves the decomposition is lossless and dependency preserving", "marks": 4},
        ],
        "model_answer": (
            "Closures: B+ = {B}. BF+ = {B,F}; F -> A adds A; A -> CD adds C and D; B -> E adds E, "
            "so BF+ = {A,B,C,D,E,F} = R and {B,F} is a key. It is minimal because no attribute can "
            "be removed: B+ = {B} and F+ = {F,A,C,D} are both proper subsets of R. No other "
            "combination works, since E is obtainable only from B, F is on no right-hand side so it "
            "must appear in every key, and A is obtainable only from F. The only candidate key is "
            "(B, F). Prime attributes are therefore B and F. For 3NF: A -> CD is non-trivial, A is "
            "not a superkey, and C and D are non-prime, so R is not in 3NF. For BCNF: the same "
            "dependency A -> CD has a determinant that is not a superkey, so R is not in BCNF. "
            "Decompose on A -> CD: R1(A, C, D) and R2(A, B, E, F). R1 has key A and is in BCNF. "
            "In R2 the dependency F -> A still has a non-superkey determinant because F+ in R2 is "
            "{F, A, E} and does not contain B, so decompose again: R2a(B, F) and R2b(F, A, E). "
            "R2a has key (B, F) with no non-trivial dependency, and R2b has key F with F -> AE. All "
            "three relations are in BCNF. Lossless join: for R -> R1, R2 the intersection is {A} and "
            "A -> CD determines R1, so the join is lossless; for R2 -> R2a, R2b the intersection is "
            "{F} and F -> AE determines R2b, so that join is also lossless; composing the two steps "
            "gives a lossless join of the three relations. Dependency preservation: A -> CD is "
            "enforced entirely inside R1, and both B -> E and F -> A are enforced entirely inside "
            "R2b, so no join is needed to check any dependency of F."
        ),
    },
    {
        "question_no": "02",
        "bloom_level": "Understand",
        "max_marks": 20,
        "question_text": (
            "(a) The statement \"In a Type 2 JDBC driver a vendor specific driver must be "
            "installed on each client machine\" is given. Accept or refute it and justify your "
            "answer. (b) Consider the code segment String query = \"Update Employee SET type = ? "
            "WHERE empId = ?\"; PreparedStatement psObject = connObj.prepareStatement(query); "
            "ResultSet rsObject = psObject.executeQuery(); State which JDBC statement type is used "
            "and explain when this type of statement is used. (c) Briefly explain two types of "
            "backup that could be taken in SQL Server. (d) Briefly explain what schedules and jobs "
            "are, suggest a situation where using a schedule is useful, and state when the "
            "schedule will be executed. (20 marks)"
        ),
        "criteria": [
            {"point": "Accepts the Type 2 JDBC statement with vendor-specific client-side justification", "marks": 4},
            {"point": "Identifies PreparedStatement and explains placeholders, binding and reuse", "marks": 4},
            {"point": "Explains two SQL Server backup types with correct characteristics", "marks": 4},
            {"point": "Explains SQL Server Agent jobs and schedules with a scenario and execution time", "marks": 4},
            {"point": "Organises the answer into labelled parts a, b, c and d with correct terminology", "marks": 4},
        ],
        "model_answer": (
            "(a) The statement is accepted. A Type 2 driver is vendor specific, is partly written in "
            "Java and partly in native code, and therefore the vendor's own client-side driver "
            "library, for example the Oracle client or the DB2 CLI, must be installed and configured "
            "on every client machine that connects to the database. This is unlike Type 4, which is "
            "pure Java and needs nothing installed on the client. "
            "(b) The code uses a PreparedStatement. The question marks are parameter placeholders, "
            "the values are supplied later through setString or setInt, and the SQL text is compiled "
            "once by the driver so it can be executed many times with different values. This type of "
            "statement is used when the same query is executed repeatedly inside a loop, when user "
            "input has to be passed without concatenating strings, and when the query plan can be "
            "reused. It also protects against SQL injection because the input is never parsed as "
            "part of the SQL text. A separate small point is that an UPDATE is normally run with "
            "executeUpdate rather than executeQuery, since executeQuery expects a result set. "
            "(c) Two backup types are a full backup, which copies all data, all objects and the "
            "transaction log, and can be restored completely on its own; and a differential or "
            "incremental backup, which copies only the data pages that have changed since the last "
            "full backup, so it is small and fast and must be restored together with its base full "
            "backup. A third useful type is the transaction log backup, which records every "
            "transaction since the previous log backup and allows point-in-time recovery. "
            "(d) A job in SQL Server Agent is a sequence of one or more steps that the Agent "
            "executes, for example an UPDATE statement followed by an EXEC of a maintenance "
            "procedure. A schedule is a set of rules that defines when Agent starts that job, for "
            "example every day at 02:00 or on the first day of every month. A schedule is useful "
            "whenever work must happen unattended at a predictable time, for example reindexing the "
            "database every night, deleting audit records older than a year every month, or taking a "
            "full backup at the weekend. The schedule is evaluated by the SQL Server Agent service "
            "and the job starts automatically at the next matching time when the Agent service and "
            "the server are running. The answer is organised as parts a, b, c and d, using "
            "PreparedStatement and executeQuery for the JDBC half and full backup, differential "
            "backup, transaction log backup and SQL Server Agent for the SQL Server half."
        ),
    },
    {
        "question_no": "03",
        "bloom_level": "Apply",
        "max_marks": 20,
        "question_text": (
            "A software company is automating the tasks of a leading private school. The database "
            "must maintain records of students, staff, student marks and timetables. Kasuni, a senior "
            "DBA, handles all server administration for the database architect. Kasuni creates the "
            "database and assigns Saman the responsibility of managing the SchoolDB. Because there "
            "are many users, Aruni is given the responsibility of handling logins. Saman assigns "
            "Thusitha the responsibility of creating tables and of creating the views, stored "
            "procedures and triggers that are required. Lasitha, a data entry operator, is given the "
            "responsibility of inserting data into the tables. Lasantha is assigned the "
            "responsibility of generating reports from the data, either by querying the tables "
            "directly or by calling functions and procedures. Using T-SQL, write the statements "
            "required to: (i) create a login for Kasuni; (ii) use a fixed server role to give Kasuni "
            "authority over all administrative tasks on the server; (iii) using a user defined "
            "server role, give the user named saman.a the responsibility of handling the SchoolDB; "
            "(iv) give the login named thusitha.p permission to create tables, functions, procedures "
            "and triggers; and (v) give the login named Lasantha.h permission to perform the report "
            "generation tasks that are his responsibility. (20 marks)"
        ),
        "criteria": [
            {"point": "Applies CREATE LOGIN for Kasuni with a valid credential option", "marks": 4},
            {"point": "Adds Kasuni to the correct fixed server role such as sysadmin", "marks": 4},
            {"point": "Creates a user defined server role and adds saman.a to it with membership", "marks": 4},
            {"point": "Maps the database login and grants object creation rights to thusitha.p", "marks": 4},
            {"point": "Grants the least privilege report rights, including EXECUTE, to Lasantha.h", "marks": 4},
        ],
        "model_answer": (
            "(i) CREATE LOGIN Kasuni WITH PASSWORD = 'K@$uni2022'; "
            "(ii) ALTER SERVER ROLE [sysadmin] ADD MEMBER [Kasuni]; "
            "(iii) CREATE SERVER ROLE [SchoolDBManager] AUTHORIZATION [dbo]; "
            "ALTER SERVER ROLE [SchoolDBManager] ADD MEMBER [saman.a]; "
            "ALTER SERVER ROLE [SchoolDBManager] ADD MEMBER [Kasuni]; "
            "(iv) USE SchoolDB; CREATE USER [thusitha.p] FOR LOGIN [thusitha.p]; "
            "GRANT CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE FUNCTION, CREATE TRIGGER TO [thusitha.p]; "
            "(v) CREATE USER [Lasantha.h] FOR LOGIN [Lasantha.h]; "
            "GRANT SELECT ON SCHEMA :: dbo TO [Lasantha.h]; "
            "GRANT EXECUTE ON SCHEMA :: dbo TO [Lasantha.h]; "
            "Kasuni is given the fixed server role sysadmin because she must run administrative "
            "tasks such as CREATE DATABASE and CREATE LOGIN, which are server level permissions. "
            "Saman is given a user defined server role because he manages only the SchoolDB "
            "database, and he is added to that role by ALTER SERVER ROLE ... ADD MEMBER. Thusitha "
            "needs database level DDL permission through CREATE TABLE, CREATE VIEW, CREATE "
            "PROCEDURE, CREATE FUNCTION and CREATE TRIGGER, and she must first be mapped to the "
            "database as a user. Lasantha only reads data and calls stored procedures and functions, "
            "so he needs SELECT on the schema and EXECUTE to call them; he is deliberately not "
            "given INSERT because insertion is Lasitha's job."
        ),
    },
    {
        "question_no": "04",
        "bloom_level": "Apply",
        "max_marks": 20,
        "question_text": (
            "Consider the schema of a database designed for a manufacturing company. "
            "Customer(CID int, name varchar(50), gender char(1), address varchar(50), creditLimit int) "
            "with primary key CID; Manufacturer(MID char(10), name varchar(50), country varchar(50), "
            "contact char(10)) with primary key MID; Product(PID varchar(20), name varchar(50), "
            "color varchar(10), weight int, warranty int, unitPrice int, MID char(10), "
            "manufacturedDate date) with primary key PID; Order(OID char(10), CID varchar(20), "
            "orderDate date) with primary key OID; and OrderItems(OID char(10), PID varchar(20), "
            "qty int) with primary key (OID, PID). (a) Write SQL queries to (i) display the order "
            "IDs and the name of the female customers from France who placed them; (ii) find the IDs "
            "of the customers who had NOT ordered phones manufactured by manufacturers from India; "
            "and (iii) find the name and credit limit of the customers who had ordered more than "
            "10 items in a single order. (b) Create a function which calculates and returns the "
            "total price to be paid for an order given the order ID. (c) Assuming that the orders "
            "are delivered as packages, create a trigger to ensure that the weight of a package "
            "does not exceed 2 kg. (20 marks)"
        ),
        "criteria": [
            {"point": "Applies correct joins and filtering for the female customer query", "marks": 4},
            {"point": "Applies correct set difference or NOT EXISTS/NOT IN logic for the phones query", "marks": 4},
            {"point": "Aggregates order quantities with GROUP BY, HAVING and a subquery", "marks": 4},
            {"point": "Creates a single-value function that returns the total order price", "marks": 4},
            {"point": "Creates a trigger that validates package weight using the inserted pseudo-table", "marks": 4},
        ],
        "model_answer": (
            "(a)(i) SELECT O.OID, C.name FROM \"Order\" O JOIN Customer C ON O.CID = C.CID "
            "WHERE C.gender = 'F' AND C.address LIKE '%France%'; "
            "(a)(ii) SELECT CID FROM Customer WHERE CID NOT IN (SELECT O.CID FROM \"Order\" O "
            "JOIN OrderItems OI ON O.OID = OI.OID JOIN Product P ON OI.PID = P.PID JOIN Manufacturer M "
            "ON P.MID = M.MID WHERE P.name = 'phones' AND M.country = 'India'); "
            "(a)(iii) SELECT C.name, C.creditLimit FROM Customer C JOIN \"Order\" O ON C.CID = O.CID "
            "JOIN (SELECT OID, SUM(qty) AS total FROM OrderItems GROUP BY OID HAVING SUM(qty) > 10) T "
            "ON O.OID = T.OID; "
            "(b) CREATE FUNCTION dbo.TotalPrice(@OID char(10)) RETURNS int AS BEGIN DECLARE @total "
            "int; SELECT @total = SUM(P.unitPrice * OI.qty) FROM OrderItems OI JOIN Product P ON "
            "OI.PID = P.PID WHERE OI.OID = @OID; RETURN ISNULL(@total, 0); END; "
            "(c) CREATE TRIGGER trgPackageWeight ON OrderItems AFTER INSERT, UPDATE AS BEGIN SET "
            "NOCOUNT ON; IF EXISTS (SELECT 1 FROM OrderItems OI JOIN Product P ON OI.PID = P.PID "
            "WHERE OI.OID IN (SELECT OID FROM inserted) GROUP BY OI.OID HAVING SUM(P.weight * OI.qty) "
            "> 2000) BEGIN RAISERROR('Package weight cannot exceed 2kg', 16, 1); ROLLBACK "
            "TRANSACTION; END END; "
            "Order is a reserved word so it must be written as \"Order\" in standard SQL. Product "
            "weight is already stored in grams, so the 2 kg limit is compared with 2000. The "
            "trigger must be an AFTER trigger reading the inserted pseudo-table so that a single "
            "statement inserting several order items for one order is checked as a whole rather "
            "than line by line, and the grouping is by OID so each package is validated separately."
        ),
    },
    {
        "question_no": "05",
        "bloom_level": "Create",
        "max_marks": 20,
        "question_text": (
            "Design, construct, and produce a new, original logical and physical database design "
            "diagram for the manufacturing company scenario used in this paper. Show the CUSTOMER, "
            "MANUFACTURER, PRODUCT, ORDER and ORDERITEMS entities with all their attributes and "
            "clearly underlined primary keys; draw the MANUFACTURER to PRODUCT, CUSTOMER to ORDER, "
            "ORDER to ORDERITEMS and PRODUCT to ORDERITEMS relationships with correct cardinalities, "
            "optionality and crow's foot notation; mark the foreign keys; add the derived or "
            "calculated item for the total order value, an index on OrderItems(OID) and the module "
            "or trigger that validates the 2 kg package weight limit; and finish with a short design "
            "note that justifies your key and relationship choices. Use clear labels throughout. "
            "(20 marks)"
        ),
        "criteria": [
            {"point": "Creates all five core entities with the correct attributes", "marks": 4},
            {"point": "Marks the primary, foreign and composite primary keys correctly", "marks": 4},
            {"point": "Shows correct cardinalities, optionality and crow's-foot notation", "marks": 4},
            {"point": "Includes the derived total order value, the index and the validation module", "marks": 4},
            {"point": "Produces clear labels and a coherent design justification note", "marks": 4},
        ],
        "model_answer": (
            "CUSTOMER(CID PK, name, gender, address, creditLimit), MANUFACTURER(MID PK, name, country, "
            "contact), PRODUCT(PID PK, name, color, weight, warranty, unitPrice, MID FK, "
            "manufacturedDate), ORDER(OID PK, CID FK, orderDate) and ORDERITEMS(OID FK, PID FK, qty, "
            "PK(OID, PID)). MANUFACTURER is one and only PRODUCT is many, so MANUFACTURER "
            "manufactures PRODUCT is 1:N with total participation on the manufacturer side. CUSTOMER "
            "is one and ORDER is zero-to-many, so CUSTOMER places ORDER is 1:N and a customer is "
            "optional on the order side. ORDER is one and ORDERITEMS is one-to-many, and PRODUCT is "
            "one and ORDERITEMS is one-to-many, giving a many-to-many ORDER to PRODUCT relationship "
            "that is resolved by the associative entity ORDERITEMS. The derived attribute "
            "ORDER_TOTAL(OID, totalPrice) is produced by the scalar function fnOrderTotal(OID), which "
            "sums unitPrice times qty over OrderItems and Product. The physical element "
            "IX_OrderItems_OID is a clustered or non-clustered index on OrderItems(OID) supporting "
            "the package weight trigger and the order total function. The module "
            "PACKAGE_VALIDATION(OID, totalWeight, maxWeight = 2000) implemented by the trigger "
            "trgPackageWeight checks the aggregate weight of each order. The composite key "
            "(OID, PID) is used for OrderItems because a product line is identified only by the "
            "order it belongs to together with the product, and the same product may legitimately "
            "appear in many orders, so neither attribute is a key on its own."
        ),
    },
]

GUIDELINES = [
    {
        "id": 1,
        "criterion": "Creates all five core entities with the correct attributes",
        "description": "Shows Customer, Manufacturer, Product, Order and OrderItems with their attributes from the given schema.",
        "marks": 4,
    },
    {
        "id": 2,
        "criterion": "Marks the primary, foreign and composite primary keys correctly",
        "description": "Underlines the single primary keys, labels every foreign key and marks OrderItems primary key as (OID, PID).",
        "marks": 4,
    },
    {
        "id": 3,
        "criterion": "Shows correct cardinalities, optionality and crow's-foot notation",
        "description": "Uses 1:N for manufacturer-product and customer-order and resolves order to product through OrderItems.",
        "marks": 4,
    },
    {
        "id": 4,
        "criterion": "Includes the derived total order value, the index and the validation module",
        "description": "Adds the derived total price item, an index on OrderItems(OID) and the weight validation trigger or module.",
        "marks": 4,
    },
    {
        "id": 5,
        "criterion": "Produces clear labels and a coherent design justification note",
        "description": "Labels boxes and relationships clearly and explains why the chosen keys and relationships are appropriate.",
        "marks": 4,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Diagram blueprint for question 05
# ─────────────────────────────────────────────────────────────────────────────

DIAGRAM_ENTITIES = [
    {"entity_name": "CUSTOMER", "attributes": ["CID (PK)", "name", "gender", "address", "creditLimit"]},
    {"entity_name": "MANUFACTURER", "attributes": ["MID (PK)", "name", "country", "contact"]},
    {"entity_name": "PRODUCT", "attributes": ["PID (PK)", "name", "color", "weight", "warranty", "unitPrice", "MID (FK)", "manufacturedDate"]},
    {"entity_name": "ORDER", "attributes": ["OID (PK)", "CID (FK)", "orderDate"]},
    {"entity_name": "ORDERITEMS", "attributes": ["OID (FK, PK)", "PID (FK, PK)", "qty"]},
    {"entity_name": "ORDER_TOTAL (derived)", "attributes": ["OID", "totalPrice = fnOrderTotal(OID)"]},
    {"entity_name": "PACKAGE_VALIDATION", "attributes": ["OID", "totalWeight", "maxWeight = 2000 g"]},
    {"entity_name": "IX_ORDERITEMS_OID", "attributes": ["index on OrderItems(OID)", "supports trigger and function"]},
]

DIAGRAM_RELATIONS = [
    {"relation_name": "manufactures", "entities": ["MANUFACTURER", "PRODUCT"], "attributes": ["1 : N", "MID = Product.MID"]},
    {"relation_name": "places", "entities": ["CUSTOMER", "ORDER"], "attributes": ["1 : N", "CID = Order.CID"]},
    {"relation_name": "contains", "entities": ["ORDER", "ORDERITEMS"], "attributes": ["1 : N", "OID = OrderItems.OID"]},
    {"relation_name": "appears in", "entities": ["PRODUCT", "ORDERITEMS"], "attributes": ["1 : N", "PID = OrderItems.PID"]},
    {"relation_name": "is valued by", "entities": ["ORDER", "ORDER_TOTAL (derived)"], "attributes": ["1 : 1", "derived attribute"]},
    {"relation_name": "is checked by", "entities": ["ORDER", "PACKAGE_VALIDATION"], "attributes": ["1 : 1", "trigger trgPackageWeight"]},
]

DIAGRAM_NOTES = {
    "high": (
        "Design note: I chose CID, MID, PID and OID as single-attribute primary keys because each "
        "naturally identifies one customer, manufacturer, product or order. Product.MID and "
        "Order.CID are foreign keys for the two 1:N relationships. OrderItems needs the composite "
        "primary key (OID, PID) because an order line is only identified by the order together "
        "with the product, and one product may legitimately appear in many orders. The derived "
        "attribute ORDER_TOTAL is computed by fnOrderTotal(OID) and must not be stored, otherwise "
        "it can disagree with OrderItems. I added the index on OrderItems(OID) because the "
        "package weight trigger groups by OID on every delivery insert, and I validated the 2 kg "
        "limit in a trigger so the rule is enforced for every user of the database."
    ),
    "medium": (
        "Design note: the primary keys are underlined and the foreign keys are marked. Product "
        "belongs to one Manufacturer, so the manufacturer side is 1:N. A Customer can place many "
        "Orders, so that relationship is also 1:N. Order and Product are many to many through "
        "OrderItems, so OrderItems is the associative entity and its primary key is (OID, PID). "
        "The total price is derived using a function and the package weight limit is checked with "
        "a trigger."
    ),
    "low": (
        "Design note: I drew the tables as boxes and connected the lines. The keys are shown and "
        "the total price and weight are calculated by the program."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Student population
# ─────────────────────────────────────────────────────────────────────────────

# (label, ability_low, ability_high, count)
TIERS = [
    ("distinction", 0.94, 1.00, 6),
    ("strong", 0.85, 0.93, 8),
    ("competent", 0.71, 0.84, 9),
    ("developing", 0.57, 0.70, 9),
    ("weak", 0.41, 0.56, 9),
    ("very_weak", 0.25, 0.40, 6),
    ("minimal", 0.09, 0.24, 3),
]

# Per-question difficulty: how demanding each question is, relative to overall ability.
QUESTION_DIFFICULTY = {"01": 1.05, "02": 0.88, "03": 1.00, "04": 1.08, "05": 1.12}

# Skill bias per student: some students are naturally stronger at SQL than at theory, etc.
BIAS_CHOICES = [
    {}, {}, {}, {}, {},
    {"04": 0.10, "03": 0.05},
    {"01": 0.10, "05": 0.05},
    {"02": 0.10, "03": 0.06},
    {"04": -0.10, "01": 0.08},
    {"05": 0.12, "02": -0.05},
    {"03": 0.10, "02": -0.06},
]


def build_roster() -> list[dict]:
    roster = []
    idx = 0
    for label, low, high, count in TIERS:
        for _ in range(count):
            idx += 1
            ability = low + (high - low) * ((idx % 7) / 6.0)
            ability = round(min(0.995, max(0.05, ability)), 4)
            roster.append({
                "index": idx,
                "student_id": STUDENT_IDS[idx - 1],
                "tier": label,
                "ability": ability,
                "bias": dict(BIAS_CHOICES[idx % len(BIAS_CHOICES)]),
            })
    return roster


# ─────────────────────────────────────────────────────────────────────────────
# 4. Answer banks — one entry per rubric criterion, per quality level
# ─────────────────────────────────────────────────────────────────────────────

# Levels used everywhere: "full", "partial", "weak", "none"
BANKS: dict[str, list[dict]] = {
    "01": [
        {
            "full": [
                "a) Attribute closure. B+ = {B}, so B alone is not a key. F+ = {F, A, C, D}, so F alone is not a key either.",
                "Starting from BF, the closure grows as BF+ = {B,F}; F -> A adds A giving {A,B,F}; A -> CD adds C and D giving {A,B,C,D,F}; B -> E adds E, so BF+ = {A,B,C,D,E,F} = R.",
                "Both attributes are needed, so (B, F) is minimal and is the only candidate key. The prime attributes are B and F.",
            ],
            "partial": [
                "a) I used attribute closure. BF gives all the attributes, so the key is (B, F).",
                "BF+ = {B,F} then F -> A gives A, A -> CD gives C and D, and B -> E gives E, so BF+ = R.",
            ],
            "weak": [
                "a) The key is (B, F) because F gives A and then C and D, and B gives E.",
                "I think the primary key is BF.",
            ],
            "none": ["a) The key is A."],
        },
        {
            "full": [
                "b) R is not in 3NF. Take the non-trivial dependency A -> CD. The determinant A is not a superkey of R, and neither C nor D is a prime attribute, because the only prime attributes are B and F. The 3NF test therefore fails for A -> CD, so R is only in 1NF as it stands.",
            ],
            "partial": [
                "b) R is not in 3NF because A -> CD has a determinant that is not a superkey and CD contains non-prime attributes.",
            ],
            "weak": [
                "b) R is in 3NF because the FDs are all satisfied.",
                "R is in 3NF since every dependency goes from A or B to other attributes.",
            ],
            "none": ["b) R is in 3NF."],
        },
        {
            "full": [
                "c) R is not in BCNF either. BCNF requires the determinant of every non-trivial dependency to be a superkey. A -> CD has determinant A, and A+ = {A, C, D} is a proper subset of R, so this dependency violates BCNF. The same reasoning applies to F -> A, whose determinant F is not a superkey once the relation is decomposed.",
            ],
            "partial": [
                "c) R is not in BCNF because A -> CD and F -> A have determinants that are not superkeys.",
            ],
            "weak": [
                "c) R is not in BCNF because of A -> CD.",
                "R is not in BCNF, A is not a key.",
            ],
            "none": ["c) R is not in BCNF."],
        },
        {
            "full": [
                "d) Decompose on A -> CD: R1(A, C, D) and R2(A, B, E, F). R1 has primary key A and is in BCNF.",
                "In R2 the dependency F -> A still has a non-superkey determinant because F+ within R2 is {F, A, E} and does not contain B, so decompose again: R2a(B, F) with primary key (B, F) and R2b(F, A, E) with primary key F.",
                "R2a has no non-trivial dependency at all and R2b has only F -> AE, where F is the key, so R1, R2a and R2b are all in BCNF.",
            ],
            "partial": [
                "d) Decompose on A -> CD to get R1(A, C, D) with key A and R2(A, B, E, F). Then decompose R2 on F -> A to get R2a(B, F) and R2b(F, A, E) with keys (B, F) and F.",
            ],
            "weak": [
                "d) R1(A, C, D) with key A and R2(A, B, E, F). I am not sure about the keys.",
            ],
            "none": ["d) Split into two relations."],
        },
        {
            "full": [
                "e) Lossless join: for R -> R1, R2 the intersection is {A} and A -> CD determines R1, so the binary decomposition is lossless. For R2 -> R2a, R2b the intersection is {F} and F -> AE determines R2b, so that step is also lossless, and composing the two steps gives a lossless join of the three relations.",
                "e) Dependency preservation: A -> CD is checked entirely inside R1, and B -> E and F -> A are checked entirely inside R2b, so no join is required to verify any dependency of the original set.",
            ],
            "partial": [
                "e) The intersection of R1 and R2 is A and A -> CD, so the join is lossless. A -> CD stays in R1 and B -> E and F -> A stay in R2b, so dependencies are preserved.",
            ],
            "weak": [
                "e) The join is lossless and the dependencies are preserved.",
            ],
            "none": [],
        },
    ],
    "02": [
        {
            "full": [
                "a) The statement is accepted. A Type 2 JDBC driver is vendor specific and is only partly written in Java; the rest is native code that talks to the vendor client library, so the vendor driver must be installed and configured on every client machine. This is the difference from a Type 4 driver, which is pure Java and needs nothing installed on the client.",
            ],
            "partial": [
                "a) Accept. The statement is correct because a Type 2 driver is vendor specific and must be installed on the client.",
            ],
            "weak": [
                "a) Accept because the vendor specific driver is used.",
                "a) True, it depends on the vendor driver.",
            ],
            "none": ["a) Accept."],
        },
        {
            "full": [
                "b) The code uses a PreparedStatement, obtained from connObj.prepareStatement(query). The question marks are parameter placeholders; the values are supplied afterwards with setString or setInt, and the SQL text is compiled once by the driver so it can be executed again with different values.",
                "b) This type of statement is used when the same query runs repeatedly inside a loop, when user input has to be passed without building the SQL by string concatenation, and when the compiled plan should be reused. It is also safe against SQL injection because the bound values are never parsed as SQL. A small correction: an UPDATE normally calls executeUpdate rather than executeQuery, since executeQuery expects a result set.",
            ],
            "partial": [
                "b) It is a PreparedStatement. The ? marks are placeholders for the values, which are set later, and the prepared statement can be executed many times.",
            ],
            "weak": [
                "b) It is a PreparedStatement and it is used for queries that run many times.",
                "b) This is a PreparedStatement used when values change.",
            ],
            "none": ["b) It is a statement type."],
        },
        {
            "full": [
                "c) A full backup copies all the data, all the objects and the transaction log, and it can be restored completely on its own. A differential or incremental backup copies only the data pages that have changed since the last full backup, so it is small and fast, and it must be restored together with its base full backup. A third type is the transaction log backup, which records every transaction since the previous log backup and allows recovery to a point in time.",
            ],
            "partial": [
                "c) Full backup copies everything including the log and can be restored on its own. An incremental backup copies only the data changed since the last full backup.",
            ],
            "weak": [
                "c) Full backup and incremental backup.",
                "c) Full backup and differential backup.",
            ],
            "none": ["c) Full backup."],
        },
        {
            "full": [
                "d) A job in SQL Server Agent is a sequence of one or more steps that Agent executes, for example an UPDATE followed by EXEC of a maintenance stored procedure. A schedule is the set of rules that says when Agent starts that job, for example every day at 02:00 or on the first day of every month.",
                "d) A schedule is useful whenever work has to run unattended at a predictable time, for example reindexing the database every night, deleting audit rows older than a year every month, or taking a full backup over the weekend. The schedule is evaluated by the SQL Server Agent service, so the job starts automatically at the next matching time as long as the Agent service and the instance are running.",
            ],
            "partial": [
                "d) A job is a set of steps run by SQL Server Agent and a schedule says when it runs, for example every night at 02:00. It is useful for unattended work such as a nightly backup or reindexing.",
            ],
            "weak": [
                "d) A job is a task and a schedule is the time for it. It runs at the scheduled time.",
            ],
            "none": ["d) A schedule runs the job."],
        },
        {
            "full": [
                "The four parts are answered separately as (a), (b), (c) and (d). The terminology I have used is PreparedStatement for the JDBC object and executeQuery for retrieving the result set.",
                "On the SQL Server side the names I have used are full backup, differential backup and transaction log backup, and SQL Server Agent as the component that owns jobs and schedules.",
            ],
            "partial": [
                "I answered the parts as a, b, c and d using the terms PreparedStatement, backup, job and schedule.",
            ],
            "weak": [
                "The JDBC part and the server part are answered.",
            ],
            "none": [],
        },
    ],
    "03": [
        {
            "full": [
                "i) CREATE LOGIN Kasuni WITH PASSWORD = 'K@$uni2022'; This creates the server level login. I also add DEFAULT DATABASE = [SchoolDB] so that Kasuni lands in the right database.",
                "i) A login is a server level principal, so CREATE LOGIN is the correct statement; a user is the database level counterpart and is created later with CREATE USER.",
            ],
            "partial": [
                "i) CREATE LOGIN Kasuni WITH PASSWORD = 'K@$uni2022';",
            ],
            "weak": ["i) CREATE LOGIN Kasuni;", "i) CREATE USER Kasuni;"],
            "none": ["i) Kasuni login created."],
        },
        {
            "full": [
                "ii) ALTER SERVER ROLE [sysadmin] ADD MEMBER [Kasuni]; sysadmin is the fixed server role that has authority over all administrative tasks on the server, such as CREATE DATABASE, CREATE LOGIN and changing server settings. Membership is added with ALTER SERVER ROLE ... ADD MEMBER and can be removed the same way.",
            ],
            "partial": [
                "ii) ALTER SERVER ROLE [sysadmin] ADD MEMBER [Kasuni]; the sysadmin fixed server role is used for all administrative tasks.",
            ],
            "weak": [
                "ii) ADD Kasuni TO sysadmin;",
                "ii) GRANT ALL TO Kasuni;",
            ],
            "none": ["ii) Kasuni is the administrator."],
        },
        {
            "full": [
                "iii) CREATE SERVER ROLE [SchoolDBManager] AUTHORIZATION [dbo]; creates the user defined server role. ALTER SERVER ROLE [SchoolDBManager] ADD MEMBER [saman.a]; then adds the login saman.a to it, and ALTER SERVER ROLE [SchoolDBManager] ADD MEMBER [Kasuni]; lets Kasuni hand out membership. Finally USE SchoolDB; and ALTER ROLE [SchoolDBManager] ADD MEMBER [saman.a]; give the role inside the database.",
            ],
            "partial": [
                "iii) CREATE SERVER ROLE [SchoolDBManager]; ALTER SERVER ROLE [SchoolDBManager] ADD MEMBER [saman.a];",
            ],
            "weak": [
                "iii) CREATE ROLE SchoolDBManager; ADD saman.a TO SchoolDBManager;",
                "iii) CREATE SERVER ROLE SchoolDBManager; GRANT SchoolDBManager TO saman.a;",
            ],
            "none": ["iii) Role created for Saman."],
        },
        {
            "full": [
                "iv) USE SchoolDB; CREATE USER [thusitha.p] FOR LOGIN [thusitha.p]; maps the login into the database first. GRANT CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE FUNCTION, CREATE TRIGGER TO [thusitha.p]; then gives exactly the DDL permissions Thusitha needs. She is deliberately not made a db_owner, because db_owner would also let her drop the database.",
            ],
            "partial": [
                "iv) USE SchoolDB; CREATE USER [thusitha.p] FOR LOGIN [thusitha.p]; GRANT CREATE TABLE, CREATE VIEW, CREATE PROCEDURE, CREATE TRIGGER TO [thusitha.p];",
            ],
            "weak": [
                "iv) GRANT ALL TO thusitha.p;",
                "iv) CREATE USER thusitha.p; GRANT CREATE TABLE TO thusitha.p;",
            ],
            "none": ["iv) Permissions given to Thusitha."],
        },
        {
            "full": [
                "v) CREATE USER [Lasantha.h] FOR LOGIN [Lasantha.h]; GRANT SELECT ON SCHEMA :: dbo TO [Lasantha.h]; GRANT EXECUTE ON SCHEMA :: dbo TO [Lasantha.h];",
                "v) Lasantha only generates reports, so he needs SELECT to query the tables directly and EXECUTE to call the functions and procedures. Giving INSERT or UPDATE would break the separation of duties, because inserting data is Lasitha's responsibility.",
            ],
            "partial": [
                "v) GRANT SELECT ON SCHEMA :: dbo TO [Lasantha.h]; GRANT EXECUTE ON SCHEMA :: dbo TO [Lasantha.h];",
            ],
            "weak": [
                "v) GRANT SELECT, EXECUTE TO Lasantha.h;",
                "v) GRANT SELECT TO Lasantha.h;",
            ],
            "none": ["v) Report permission given."],
        },
    ],
    "04": [
        {
            "full": [
                "a)(i) SELECT O.OID, C.name FROM \"Order\" O JOIN Customer C ON O.CID = C.CID WHERE C.gender = 'F' AND C.address LIKE '%France%';",
                "a)(i) Order is a reserved keyword, so it must be written as \"Order\" in standard SQL. The join is on the foreign key CID and the two filters select female customers whose address contains France.",
            ],
            "partial": [
                "a)(i) SELECT O.OID, C.name FROM \"Order\" O, Customer C WHERE O.CID = C.CID AND C.gender = 'F' AND C.address LIKE '%France%';",
            ],
            "weak": [
                "a)(i) SELECT OID, name FROM Order, Customer WHERE gender = 'F' AND address LIKE '%France%';",
                "a)(i) SELECT * FROM Order O JOIN Customer C ON O.CID = C.CID WHERE gender='F';",
            ],
            "none": ["a)(i) Female customers from France."],
        },
        {
            "full": [
                "a)(ii) SELECT CID FROM Customer WHERE CID NOT IN (SELECT O.CID FROM \"Order\" O JOIN OrderItems OI ON O.OID = OI.OID JOIN Product P ON OI.PID = P.PID JOIN Manufacturer M ON P.MID = M.MID WHERE P.name = 'phones' AND M.country = 'India');",
                "a)(ii) This is a set difference. NOT EXISTS with a correlated subquery would be safer than NOT IN, because NOT IN returns no rows at all if the subquery ever produces a NULL CID.",
            ],
            "partial": [
                "a)(ii) SELECT CID FROM Customer WHERE CID NOT IN (SELECT O.CID FROM \"Order\" O, OrderItems OI, Product P, Manufacturer M WHERE O.OID = OI.OID AND OI.PID = P.PID AND P.MID = M.MID AND P.name = 'phones' AND M.country = 'India');",
            ],
            "weak": [
                "a)(ii) SELECT CID FROM Customer WHERE CID NOT IN (SELECT CID FROM \"Order\" WHERE ...);",
                "a)(ii) SELECT CID FROM Customer EXCEPT SELECT CID FROM \"Order\";",
            ],
            "none": ["a)(ii) Customers who did not order phones."],
        },
        {
            "full": [
                "a)(iii) SELECT C.name, C.creditLimit FROM Customer C JOIN \"Order\" O ON C.CID = O.CID JOIN (SELECT OID, SUM(qty) AS total FROM OrderItems GROUP BY OID HAVING SUM(qty) > 10) T ON O.OID = T.OID;",
                "a)(iii) The subquery aggregates the quantities per order and keeps only the orders above the threshold with HAVING, because the condition applies to the group and not to a single row. SUM must be repeated in HAVING since the alias cannot be used there in standard SQL.",
            ],
            "partial": [
                "a)(iii) SELECT C.name, C.creditLimit FROM Customer C JOIN \"Order\" O ON C.CID = O.CID JOIN OrderItems OI ON O.OID = OI.OID GROUP BY C.name, C.creditLimit, O.OID HAVING SUM(OI.qty) > 10;",
            ],
            "weak": [
                "a)(iii) SELECT name, creditLimit FROM Customer WHERE ... ;",
                "a)(iii) SELECT C.name, C.creditLimit FROM Customer C JOIN \"Order\" O ON C.CID = O.CID WHERE O.OID IN (SELECT OID FROM OrderItems GROUP BY OID HAVING SUM(qty) > 10);",
            ],
            "none": ["a)(iii) Customers with more than 10 items."],
        },
        {
            "full": [
                "b) CREATE FUNCTION dbo.TotalPrice(@OID char(10)) RETURNS int AS BEGIN DECLARE @total int; SELECT @total = SUM(P.unitPrice * OI.qty) FROM OrderItems OI JOIN Product P ON OI.PID = P.PID WHERE OI.OID = @OID; RETURN ISNULL(@total, 0); END;",
                "b) It is a single valued scalar function because it returns one number for the given order ID. ISNULL returns 0 for an order with no items instead of NULL, so the report does not break.",
            ],
            "partial": [
                "b) CREATE FUNCTION dbo.TotalPrice(@OID char(10)) RETURNS int AS BEGIN RETURN (SELECT SUM(P.unitPrice * OI.qty) FROM OrderItems OI, Product P WHERE OI.PID = P.PID AND OI.OID = @OID); END;",
            ],
            "weak": [
                "b) CREATE FUNCTION TotalPrice(@OID char(10)) RETURNS int AS BEGIN SELECT SUM(P.unitPrice*OI.qty) FROM OrderItems OI JOIN Product P ON OI.PID=P.PID WHERE OI.OID=@OID; END;",
            ],
            "none": ["b) A function to calculate the total price."],
        },
        {
            "full": [
                "c) CREATE TRIGGER trgPackageWeight ON OrderItems AFTER INSERT, UPDATE AS BEGIN SET NOCOUNT ON; IF EXISTS (SELECT 1 FROM OrderItems OI JOIN Product P ON OI.PID = P.PID WHERE OI.OID IN (SELECT OID FROM inserted) GROUP BY OI.OID HAVING SUM(P.weight * OI.qty) > 2000) BEGIN RAISERROR('Package weight cannot exceed 2kg', 16, 1); ROLLBACK TRANSACTION; END END;",
                "c) Product.weight is already in grams, so 2 kg is compared with 2000. The trigger is an AFTER trigger that reads the inserted pseudo-table, so one statement adding several order items to the same order is validated as a whole package, and the GROUP BY OID checks every affected package separately. ROLLBACK undoes the offending statement automatically.",
            ],
            "partial": [
                "c) CREATE TRIGGER trgPackageWeight ON OrderItems AFTER INSERT AS BEGIN IF (SELECT SUM(P.weight * OI.qty) FROM inserted OI JOIN Product P ON OI.PID = P.PID) > 2000 RAISERROR('Too heavy', 16, 1); ROLLBACK TRANSACTION; END;",
            ],
            "weak": [
                "c) CREATE TRIGGER trgWeight ON OrderItems AFTER INSERT AS BEGIN IF EXISTS(SELECT 1 FROM inserted WHERE qty > 10) PRINT 'error'; END;",
                "c) ALTER TABLE OrderItems ADD CHECK (weight <= 2000);",
            ],
            "none": ["c) A trigger to check the weight."],
        },
    ],
}


# Question 05 is answered with a drawing plus a short note; keep the variants shorter.
BANKS["05"] = [
    {  # 1 - all five core entities
        "full": [
            "Drawn boxes: CUSTOMER(CID, name, gender, address, creditLimit), MANUFACTURER(MID, name, country, contact), PRODUCT(PID, name, color, weight, warranty, unitPrice, MID, manufacturedDate), ORDER(OID, CID, orderDate) and ORDERITEMS(OID, PID, qty). I copied every attribute from the schema in the question and did not add any invented columns.",
        ],
        "partial": [
            "I drew CUSTOMER, MANUFACTURER, PRODUCT, ORDER and ORDERITEMS with their attributes.",
        ],
        "weak": [
            "I drew the tables Customer, Manufacturer, Product, Order and OrderItems as boxes.",
        ],
        "none": ["I drew the diagram on page 4."],
    },
    {  # 2 - keys
        "full": [
            "Keys are underlined in red: CID, MID, PID and OID are single attribute primary keys. Product.MID and Order.CID are foreign keys shown with a small FK tag. OrderItems has the composite primary key (OID, PID) because an order line is identified by the order together with the product.",
        ],
        "partial": [
            "The primary keys are underlined and the foreign keys are marked. OrderItems has the key (OID, PID).",
        ],
        "weak": [
            "The keys are underlined. OrderItems key is OID and PID.",
        ],
        "none": ["Keys are shown in the boxes."],
    },
    {  # 3 - cardinalities
        "full": [
            "MANUFACTURER 1 --< PRODUCT with a crow's foot and a bar on the manufacturer side, so one manufacturer makes many products and each product has exactly one manufacturer.",
            "CUSTOMER 1 --o< ORDER, the crow's foot with a circle because a customer may have no orders yet.",
            "ORDER 1 --< ORDERITEMS and PRODUCT 1 --< ORDERITEMS, which resolves the many to many between order and product through the associative entity OrderItems.",
        ],
        "partial": [
            "I used crow's foot notation. Manufacturer to product is 1:N, customer to order is 1:N, and order to OrderItems is 1:N.",
        ],
        "weak": [
            "I drew lines between the tables to show the relationships, one to many.",
        ],
        "none": ["The relationships are drawn as lines."],
    },
    {  # 4 - derived value, index and module
        "full": [
            "Dashed oval for the derived attribute ORDER_TOTAL, calculated by the scalar function fnOrderTotal(OID) which sums unitPrice times qty over OrderItems and Product.",
            "A cylinder marked IX_ORDERITEMS_OID for the index on OrderItems(OID), which the trigger and the function both need because they group by OID.",
            "A box PACKAGE_VALIDATION(OID, totalWeight, maxWeight = 2000) implemented by the trigger trgPackageWeight, showing that the 2 kg rule is enforced inside the database.",
        ],
        "partial": [
            "I added the derived total price computed by a function and the trigger that checks the 2 kg weight.",
        ],
        "weak": [
            "I added the total price and the weight check.",
        ],
        "none": ["The total is calculated by the program."],
    },
    {  # 5 - labels and design note
        "full": [DIAGRAM_NOTES["high"]],
        "partial": [DIAGRAM_NOTES["medium"]],
        "weak": [DIAGRAM_NOTES["low"]],
        "none": [],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Answer quality model
# ─────────────────────────────────────────────────────────────────────────────

MARK_BY_LEVEL = {"full": (4, 4), "partial": (2, 3), "weak": (0, 1), "none": (0, 0)}

LEVEL_ORDER = ["full", "partial", "weak", "none"]


def pick_levels(ability_q: float, rng: random.Random, n: int = 5) -> list[str]:
    """Choose an answer level for each of the five rubric criteria."""
    if ability_q >= 0.90:
        weights = (0.86, 0.11, 0.03, 0.00)
    elif ability_q >= 0.78:
        weights = (0.56, 0.31, 0.12, 0.01)
    elif ability_q >= 0.64:
        weights = (0.30, 0.40, 0.25, 0.05)
    elif ability_q >= 0.50:
        weights = (0.12, 0.34, 0.40, 0.14)
    elif ability_q >= 0.36:
        weights = (0.03, 0.20, 0.45, 0.32)
    elif ability_q >= 0.20:
        weights = (0.00, 0.09, 0.38, 0.53)
    else:
        weights = (0.00, 0.02, 0.22, 0.76)

    return [rng.choices(LEVEL_ORDER, weights=weights, k=1)[0] for _ in range(n)]


def award(level: str, rng: random.Random) -> int:
    lo, hi = MARK_BY_LEVEL[level]
    if lo == hi:
        return lo
    return rng.randint(lo, hi)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Script prose helpers
# ─────────────────────────────────────────────────────────────────────────────

FILLER = [
    "I am not sure about this part.",
    "This is my understanding of the question.",
    "I wrote whatever I could remember.",
    "Sorry for the handwriting.",
    "I did not have time to check this again.",
    "According to my notes this is correct.",
    "I wrote this from the class notes.",
    "Please check part of this answer.",
]

MISCONCEPTIONS = [
    "I used ORDER instead of \"Order\" because I did not remember that it is a reserved word.",
    "I am not sure whether weight is already in grams in the schema.",
    "I did not remember how attribute closure works so I guessed the key.",
    "I mixed up the fixed server roles and the database roles here.",
    "I used executeQuery because I copied it from the question.",
    "I could not remember the exact syntax of ALTER SERVER ROLE.",
]


def bank_variants(bank: dict, level: str) -> list[str]:
    """Return the text variants available for a quality level (may be empty)."""
    return bank.get(level) or []


def compose_fragment(rng: random.Random, bank: dict, level: str) -> str:
    """Pick the wording a student of this ability level would actually write."""
    pool = bank_variants(bank, level)
    if not pool:
        return ""
    if len(pool) > 1 and rng.random() < 0.30:
        # A confident answer spans several points instead of one tight sentence.
        chosen = set(rng.sample(range(len(pool)), k=rng.randint(2, len(pool))))
        return " ".join(pool[i] for i in sorted(chosen))
    text = rng.choice(pool)
    weaker = [v for level_name in ("partial", "weak") for v in bank_variants(bank, level_name)]
    if weaker and level in ("full", "partial") and rng.random() < 0.22:
        # Students often bolt a weaker restatement onto a partly correct point.
        extra = rng.choice(weaker)
        if extra not in text:
            text = f"{text} {extra}"
    return text


def build_transcript(rng: random.Random, levels: dict[str, list[str]], question_marks: dict[str, int]) -> str:
    """Render a full raw_ocr_transcript for one student."""
    lines: list[str] = []
    weak_count = sum(1 for ls in levels.values() for lv in ls if lv in ("weak", "none"))
    ability = question_marks.get("__ability__", 0.5)

    if weak_count >= 8:
        if rng.random() < 0.55:
            lines.append(rng.choice(FILLER))
        if rng.random() < 0.30:
            lines.append(rng.choice(MISCONCEPTIONS))

    for q in QUESTIONS:
        qno = q["question_no"]
        heading = f"Question {int(qno)}"
        if rng.random() < 0.5:
            lines.append(heading)
        else:
            lines.append(f"Q{int(qno)}")

        body: list[str] = []
        for idx, level in enumerate(levels[qno]):
            text = compose_fragment(rng, BANKS[qno][idx], level)
            if text:
                body.append(text)

        if rng.random() < 0.25 and ability < 0.5:
            body.insert(rng.randint(0, len(body)), rng.choice(FILLER))

        lines.extend(body)
        lines.append("")

    # Trim: very weak scripts sometimes trail off.
    if ability < 0.2 and rng.random() < 0.4 and len(lines) > 12:
        lines = lines[: len(lines) - rng.randint(1, 4)]
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Diagram detections
# ─────────────────────────────────────────────────────────────────────────────

def build_diagram_docs(rng: random.Random, ability: float, student_id: str) -> tuple[list[dict], list[dict]]:
    """Return (diagram_marking core, diagram_detection subset) for question 05."""
    if ability >= 0.85:
        n_entities, n_rel, n_idx, conf_lo = 8, 6, True, 0.93
    elif ability >= 0.70:
        n_entities, n_rel, n_idx, conf_lo = 7, 5, True, 0.88
    elif ability >= 0.52:
        n_entities, n_rel, n_idx, conf_lo = 6, 4, False, 0.81
    elif ability >= 0.34:
        n_entities, n_rel, n_idx, conf_lo = 5, 3, False, 0.72
    else:
        n_entities, n_rel, n_idx, conf_lo = 4, 2, False, 0.61

    entities = DIAGRAM_ENTITIES[:n_entities]
    relations = DIAGRAM_RELATIONS[:n_rel]
    if not n_idx:
        entities = [e for e in entities if e["entity_name"] not in ("IX_ORDERITEMS_OID",)]

    detections: list[dict] = []
    idx = 0
    col_w, col_h = 300, 42
    for col, ent in enumerate(entities):
        x = 60 + (col % 3) * (col_w + 90)
        y = 60 + (col // 3) * (col_h * (len(ent["attributes"]) + 2) + 120)
        h = col_h * (len(ent["attributes"]) + 2)
        detections.append({
            "id": str(idx), "label": "Entities",
            "bbox": [x, y, x + col_w, y + h],
            "confidence": round(rng.uniform(conf_lo, min(0.99, conf_lo + 0.07)), 2),
            "text": ent["entity_name"],
        })
        idx += 1
        for a_i, attr in enumerate(ent["attributes"]):
            ay = y + col_h * (a_i + 1)
            detections.append({
                "id": str(idx), "label": "Attributes",
                "bbox": [x + 12, ay, x + col_w - 12, ay + col_h - 4],
                "confidence": round(rng.uniform(conf_lo - 0.03, min(0.99, conf_lo + 0.05)), 2),
                "text": attr,
            })
            idx += 1

    for rel in relations:
        rx = 120 + (idx % 4) * 250
        ry = 780 + (idx // 4) * 120
        detections.append({
            "id": str(idx), "label": "Relationships",
            "bbox": [rx, ry, rx + 220, ry + 56],
            "confidence": round(rng.uniform(conf_lo - 0.05, min(0.98, conf_lo + 0.04)), 2),
            "text": f"{rel['entities'][0]} {rel['relation_name']} {rel['entities'][1]} ({rel['attributes'][0]})",
        })
        idx += 1

    structure = {
        "entities": {e["entity_name"]: {"attributes": e["attributes"]} for e in entities},
        "relationships": relations,
    }
    diagram_details = {
        "label_count": len(detections),
        "entity_count": len(entities),
        "relationship_count": len(relations),
        "detections": detections,
        "entities": entities,
        "relationships": relations,
        "structure": structure,
    }
    return diagram_details, entities


def build_diagram_criteria(rng: random.Random, student: dict) -> tuple[list[dict], int, str]:
    """Score the diagram question from the same ability profile."""
    a5 = min(1.0, max(0.0, student["ability"] * QUESTION_DIFFICULTY["05"] + student["bias"].get("05", 0.0)))
    levels = pick_levels(a5, rng)
    results = []
    total = 0
    for i, (criterion, level) in enumerate(zip(GUIDELINES, levels)):
        marks = award(level, rng)
        total += marks
        results.append({
            "criterion_id": i + 1,
            "criterion": criterion["criterion"],
            "awarded_marks": marks,
            "max_marks": 4,
            "status": {"full": "pass", "partial": "partial", "weak": "fail", "none": "fail"}[level],
            "remarks": {
                "full": "Fully demonstrated",
                "partial": "Mostly correct with a minor omission",
                "weak": "Partially demonstrated",
                "none": "Not demonstrated",
            }[level],
        })
    pct = total / 20 * 100
    if pct >= 85:
        feedback = "Complete design diagram with all entities, keys, cardinalities, the derived value, index and validation module clearly presented."
    elif pct >= 65:
        feedback = "Good design diagram; a minor element such as the index or the composite key annotation is missing."
    elif pct >= 45:
        feedback = "Recognisable design, but cardinalities, crow's-foot notation and some physical elements are only partly shown."
    elif pct >= 25:
        feedback = "Partial diagram; most required entities, keys and relationships are missing or wrongly notated."
    else:
        feedback = "Diagram does not show the required entities, keys or relationships clearly enough to award marks."
    return results, total, feedback


# ─────────────────────────────────────────────────────────────────────────────
# 8. Build everything
# ─────────────────────────────────────────────────────────────────────────────

def oid(n: int) -> dict:
    return {"$oid": f"{BASE_OID[:-2]}{n:02x}"}


def build() -> None:
    rng = random.Random(SEED)
    roster = build_roster()

    rubric = {
        "_id": {"$oid": RUBRIC_OID},
        "subject_code": SUBJECT_CODE,
        "subject_name": SUBJECT_NAME,
        "year": YEAR,
        "month": MONTH,
        "semester": SEMESTER,
        "session_name": SESSION_NAME,
        "filename": FILENAME,
        "parsed_at": PARSED_AT,
        "exam_roster": [s["student_id"] for s in roster],
        "questions": QUESTIONS,
        "examCode": EXAM_CODE,
        "guideLines": GUIDELINES,
    }

    max_per_q = [{"question_no": q["question_no"], "max_marks": float(q["max_marks"])} for q in QUESTIONS]

    submissions: list[dict] = []
    diagram_evals: list[dict] = []
    diagram_marks: list[dict] = []

    counter = 0
    for student in roster:
        sid = student["student_id"]
        ability = student["ability"]
        levels_by_q: dict[str, list[str]] = {}
        marks_by_q: dict[str, int] = {}
        results: list[dict] = []

        for q in QUESTIONS:
            qno = q["question_no"]
            a_q = min(1.0, max(0.0, ability * QUESTION_DIFFICULTY[qno] + student["bias"].get(qno, 0.0)))
            levels = pick_levels(a_q, rng)
            levels_by_q[qno] = levels

            breakdown = []
            score = 0
            for i, (criterion, level) in enumerate(zip(q["criteria"], levels)):
                marks = award(level, rng)
                score += marks
                breakdown.append({
                    "point": criterion["point"],
                    "awarded_marks": marks,
                    "max_marks": criterion["marks"],
                    "achieved": level == "full",
                })
            marks_by_q[qno] = score
            results.append({
                "question_no": qno,
                "score": score,
                "max_score": float(q["max_marks"]),
                "criteria_breakdown": breakdown,
                "bloom_level": q["bloom_level"],
            })

        marks_by_q["__ability__"] = ability
        transcript = f"Student ID: {sid}\n\n" + build_transcript(rng, levels_by_q, marks_by_q)
        total = sum(marks_by_q[q["question_no"]] for q in QUESTIONS)

        counter += 1
        submissions.append({
            "_id": oid(counter),
            "student_id": sid,
            "rubric_ref": RUBRIC_OID,
            "paper_key": f"script_{counter:02d}",
            "subject_code": SUBJECT_CODE,
            "subject_name": SUBJECT_NAME,
            "year": YEAR,
            "month": MONTH,
            "semester": SEMESTER,
            "session_name": SESSION_NAME,
            "max_marks_paper_total": 100.0,
            "max_marks_per_question": max_per_q,
            "raw_ocr_transcript": transcript,
            "evaluation": {
                "total_score": total,
                "max_score": 100,
                "results": results,
            },
            "status": "graded",
            "processed_at": PROCESSED_AT,
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT,
        })

        # ── diagram question 05 ──────────────────────────────────────────
        a5 = min(1.0, max(0.0, ability * QUESTION_DIFFICULTY["05"] + student["bias"].get("05", 0.0)))
        criteria_results, d_total, feedback = build_diagram_criteria(rng, student)
        counter += 1
        diagram_evals.append({
            "_id": oid(counter),
            "student_id": sid,
            "subject_code": SUBJECT_CODE,
            "subject_name": SUBJECT_NAME,
            "year": YEAR,
            "month": MONTH,
            "semester": SEMESTER,
            "session_name": SESSION_NAME,
            "exam_code": EXAM_CODE,
            "rubric_ref": RUBRIC_OID,
            "question_no": "05",
            "evaluation_result": {
                "total_score": d_total,
                "max_score": 20,
                "criteria_results": criteria_results,
                "overall_feedback": feedback,
                "grading_source": "sample-v4-diagram-evaluator",
            },
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT,
            "question_text": QUESTIONS[4]["question_text"],
            "bloom_level": "Create",
        })

        details, entities = build_diagram_docs(rng, a5, sid)
        counter += 1
        diagram_marks.append({
            "_id": oid(counter),
            "student_id": sid,
            "subject_code": SUBJECT_CODE,
            "subject_name": SUBJECT_NAME,
            "year": YEAR,
            "month": MONTH,
            "semester": SEMESTER,
            "session_name": SESSION_NAME,
            "exam_code": EXAM_CODE,
            "rubric_ref": RUBRIC_OID,
            "question_no": "05",
            "diagram_marks": d_total,
            "diagram_max_marks": 20,
            "diagram_details": details,
            "diagram_entity_relations": entities,
            "diagram_relations": details["relationships"],
            "remarks": feedback,
            "evaluation_result": {
                "total_score": d_total,
                "max_score": 20,
                "criteria_results": criteria_results,
                "overall_feedback": feedback,
                "grading_source": "sample-v4-diagram-evaluator",
            },
            "created_at": CREATED_AT,
            "updated_at": UPDATED_AT,
            "source": "diagram-evaluation",
            "question_text": QUESTIONS[4]["question_text"],
            "bloom_level": "Create",
        })

    # v3's courses.json carries 25-character _id values, which bson.ObjectId rejects.
    # Keep the same two courses but with valid 24-character hexadecimal ids.
    courses = [
        {"_id": {"$oid": "6c1149ab7d0e5c1a3f2b8c00"}, "code": "SE3040", "name": "Software Architecture",
         "description": "Year 3 Software Engineering module"},
        {"_id": {"$oid": "6c1149ab7d0e5c1a3f2b8c01"}, "code": "IT2040", "name": "Database Management Systems",
         "description": "Year 2 Database module"},
    ]

    write("courses", courses)
    write("rubricCollection", [rubric])
    write("submissions", submissions)
    write("diagram_evaluation", diagram_evals)
    write("diagram_marking", diagram_marks)

    print(f"students           : {len(submissions)}")
    print(f"rubric questions   : {len(QUESTIONS)}")
    scores = sorted(s["evaluation"]["total_score"] for s in submissions)
    print(f"score range        : {scores[0]} - {scores[-1]}  mean {sum(scores)/len(scores):.1f}")
    print(f"passed (>=50)      : {sum(1 for x in scores if x >= 50)}/{len(scores)}")
    d_scores = sorted(d["diagram_marks"] for d in diagram_marks)
    print(f"diagram score range: {d_scores[0]} - {d_scores[-1]}  mean {sum(d_scores)/len(d_scores):.1f}")


def write(collection: str, data: list) -> None:
    path = SAMPLE_DIR / collection / f"{collection}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(data)} docs)")


if __name__ == "__main__":
    build()
