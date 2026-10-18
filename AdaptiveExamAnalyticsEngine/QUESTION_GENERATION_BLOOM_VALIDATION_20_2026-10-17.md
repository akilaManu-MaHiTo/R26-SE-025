# Question Generation and Bloom Classification Validation — 20 Questions

Run completed: 2026-10-17T00:52:43+05:30 (Asia/Colombo).

## Purpose and method

Generate 20 fresh DBMS examination questions through the existing question generator, then classify each unchanged question text using the local trained Bloom model. DBMS was selected from the project taxonomy because no course was specified.

- Generator: **Qwen3 8B** (`qwen3:8b`, Q4_K_M), running on the connected Colab runtime.
- Generation path: `app.services.llm_service.generate_candidates` → existing Ollama client and `CandidateQuestions` schema; 10 sequential calls requesting 2 questions each.
- Generation settings: temperature **0.8**, JSON output, thinking disabled, maximum 2,048 output tokens per call; validation-only request timeout 180 seconds.
- Generation targets: all six Bloom levels, existing DBMS topics, 5–10 marks per question. No historical questions supplied; embedding similarity checks disabled for this run.
- Classifier: `app.classifier.bloom_classifier.predict_bloom_batch`, local `models/bloom_modernbert/bloom.safetensors`, model version `modernbert-bloom-v1`, CPU inference.
- Classifier maximum input length: **512 tokens**. Low-confidence review threshold: **60%**; predictions below it are retained and flagged.
- Only question text was sent to the Bloom classifier; requested levels, generator labels, answers and rubrics were excluded from classifier input.
- Application code, environment configuration and databases were not changed. Requests used the current Colab tunnel only within this validation process.

## Results summary

| Measure | Result |
|---|---|
| Fresh questions generated and classified | 20 / 20 |
| Distinct question texts (case/whitespace normalized) | 20 / 20 |
| Requested topics, generated labels and mark ranges satisfied | 20 / 20 |
| Requested/generated Bloom label agrees with classifier | 15 / 20 (75.0%) |
| Label disagreements requiring review | 5 / 20 |
| Mean top-class model confidence | 78.02% |
| Predictions below 60% confidence | 4 / 20 |
| Inputs exceeding 512 tokens | 0 / 20 |

**Interpretation:** Agreement is consistency between the generation target and the classifier, not measured classification accuracy. Generator labels are provisional, and confidence is a model softmax score, not a calibrated probability of correctness. A lecturer must independently label the questions to establish accuracy.

## Coverage and agreement by requested level

| Requested level | Questions | Matching predictions | Agreement |
|---|---:|---:|---:|
| Remember | 4 | 3 | 75.0% |
| Understand | 4 | 3 | 75.0% |
| Apply | 4 | 3 | 75.0% |
| Analyze | 4 | 4 | 100.0% |
| Evaluate | 2 | 0 | 0.0% |
| Create | 2 | 2 | 100.0% |

## Confusion matrix

Rows are requested/generated labels; columns are ModernBERT predictions.

| Requested / predicted | Remember | Understand | Apply | Analyze | Evaluate | Create |
|---|---:|---:|---:|---:|---:|---:|
| Remember | 3 | 1 | 0 | 0 | 0 | 0 |
| Understand | 0 | 3 | 0 | 1 | 0 | 0 |
| Apply | 0 | 1 | 3 | 0 | 0 | 0 |
| Analyze | 0 | 0 | 0 | 4 | 0 | 0 |
| Evaluate | 0 | 0 | 0 | 2 | 0 | 0 |
| Create | 0 | 0 | 0 | 0 | 0 | 2 |

## Per-question results

| ID | Requested/generated | Predicted | Confidence | Agreement | Review |
|---|---|---|---:|---|---|
| Q01 | Remember | Remember | 91.14% | Match | Routine lecturer review |
| Q02 | Remember | Understand | 54.77% | Mismatch | Label disagreement, Low confidence |
| Q03 | Understand | Understand | 86.29% | Match | Routine lecturer review |
| Q04 | Understand | Analyze | 48.00% | Mismatch | Label disagreement, Low confidence |
| Q05 | Apply | Apply | 90.07% | Match | Routine lecturer review |
| Q06 | Apply | Apply | 81.53% | Match | Missing schema in question |
| Q07 | Analyze | Analyze | 47.18% | Match | Low confidence; answer loses Salary |
| Q08 | Analyze | Analyze | 85.78% | Match | Routine lecturer review |
| Q09 | Evaluate | Analyze | 96.36% | Mismatch | Label disagreement |
| Q10 | Evaluate | Analyze | 94.08% | Mismatch | Label disagreement |
| Q11 | Create | Create | 99.78% | Match | Routine lecturer review |
| Q12 | Create | Create | 69.46% | Match | Routine lecturer review |
| Q13 | Remember | Remember | 90.41% | Match | Routine lecturer review |
| Q14 | Remember | Remember | 95.20% | Match | Routine lecturer review |
| Q15 | Understand | Understand | 77.53% | Match | Routine lecturer review |
| Q16 | Understand | Understand | 53.75% | Match | Low confidence |
| Q17 | Apply | Understand | 62.13% | Mismatch | Label disagreement |
| Q18 | Apply | Apply | 62.97% | Match | Routine lecturer review |
| Q19 | Analyze | Analyze | 96.66% | Match | Routine lecturer review |
| Q20 | Analyze | Analyze | 77.36% | Match | Routine lecturer review |

## Review findings

- **Bloom disagreements:** Q02 (Remember → Understand), Q04 (Understand → Analyze), Q09 and Q10 (Evaluate → Analyze), and Q17 (Apply → Understand).
- **Evaluate coverage needs investigation:** neither of the two Evaluate-targeted questions was predicted as Evaluate. Their Analyze confidence scores were 96.36% and 94.08%. Independent lecturer labels are needed to determine whether generation, classification, or both need improvement.
- **Low-confidence predictions:** Q02, Q04, Q07 and Q16 fell below 60%; two of these still matched their requested level.
- **Q06 — missing schema:** the generated answer queries `Departments(DepartmentID, DepartmentName)`, but the question supplies only `Employees(EmployeeID, Name, DepartmentID, Salary)`. Supply the department lookup schema or a Sales department identifier before use.
- **Q07 — answer does not preserve the supplied schema:** the generated decomposition omits the original `Salary` attribute and introduces `DeptName`, which the question never supplies. No functional dependencies are stated. Revise the question and model answer before use.
- These content observations come from inspecting the saved text; they are not independent lecturer ground truth or a comprehensive review of all answers. The generated outputs below are preserved unchanged.

## Generated questions and model outputs

### Q01 — Introduction to DBMS & Conceptual Database Design

Define the term 'Database Management System (DBMS)' and list any three key functions it performs.

- **Marks:** 5
- **Requested/generated Bloom level:** Remember
- **Predicted Bloom level:** Remember (BT1)
- **Classifier confidence:** 91.14%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 91.14%; Understand: 8.54%; Apply: 0.13%; Analyze: 0.17%; Evaluate: 0.01%; Create: 0.01%

**Generator rationale (unverified):** This question assesses the student's ability to recall the basic definition and core functionalities of a DBMS, which is fundamental to understanding the subject.

**Generated model answer (unverified):**

A Database Management System (DBMS) is a software system that enables the creation, maintenance, and use of a database. Three key functions of a DBMS include data storage and retrieval, data security, and data integrity.

**Generated rubric criteria (unverified):**

- Correct definition of DBMS
- Listing of three functions
- Clarity of response

### Q02 — Introduction to DBMS & Conceptual Database Design

Explain the purpose of a conceptual database design and mention one common technique used for it.

- **Marks:** 10
- **Requested/generated Bloom level:** Remember
- **Predicted Bloom level:** Understand (BT2)
- **Classifier confidence:** 54.77%
- **Agreement:** Mismatch
- **Below review threshold:** Yes
- **Class scores:** Remember: 39.78%; Understand: 54.77%; Apply: 2.04%; Analyze: 2.54%; Evaluate: 0.43%; Create: 0.44%

**Generator rationale (unverified):** This question tests the student's ability to recall the purpose and techniques used in conceptual database design, which is an essential part of the DBMS curriculum.

**Generated model answer (unverified):**

The purpose of conceptual database design is to create a high-level model of the data that represents the real-world entities and their relationships without considering the physical implementation details. A common technique used for conceptual design is the Entity-Relationship (ER) model.

**Generated rubric criteria (unverified):**

- Explanation of the purpose of conceptual design
- Identification of a common technique
- Accuracy of the explanation

### Q03 — Logical Database Design

Explain the purpose of entity-relationship diagrams (ERDs) in logical database design. How do they assist in representing the structure of a database?

- **Marks:** 7.5
- **Requested/generated Bloom level:** Understand
- **Predicted Bloom level:** Understand (BT2)
- **Classifier confidence:** 86.29%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 8.59%; Understand: 86.29%; Apply: 0.67%; Analyze: 4.26%; Evaluate: 0.14%; Create: 0.04%

**Generator rationale (unverified):** This question tests the understanding of the role of ERDs in logical database design and their contribution to structuring the database.

**Generated model answer (unverified):**

Entity-Relationship Diagrams (ERDs) are used to visually represent the logical structure of a database by showing entities, their attributes, and the relationships between them. They assist in organizing data into a coherent model that reflects the real-world entities and their interactions, making it easier to design and communicate the database structure.

**Generated rubric criteria (unverified):**

- Explanation of ERD purpose
- Role in representing database structure
- Clarity and completeness

### Q04 — Logical Database Design

Differentiate between entity integrity and referential integrity in the context of logical database design. Provide one example for each.

- **Marks:** 8
- **Requested/generated Bloom level:** Understand
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 48.00%
- **Agreement:** Mismatch
- **Below review threshold:** Yes
- **Class scores:** Remember: 3.62%; Understand: 46.66%; Apply: 0.86%; Analyze: 48.00%; Evaluate: 0.71%; Create: 0.14%

**Generator rationale (unverified):** This question assesses the understanding of two fundamental integrity constraints in logical database design and the ability to provide relevant examples.

**Generated model answer (unverified):**

Entity integrity ensures that each entity has a unique identifier (primary key), such as the student ID in a student table. Referential integrity ensures that relationships between tables are maintained, such as ensuring that a foreign key in an order table references a valid primary key in a customer table.

**Generated rubric criteria (unverified):**

- Definition of entity integrity
- Definition of referential integrity
- Relevance of examples

### Q05 — Structured Query Language (SQL)

You are given a table named 'Sales' with columns 'SaleID', 'ProductID', 'Quantity', and 'SaleDate'. Write an SQL query to calculate the total quantity sold for each product in the month of June 2023.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Apply
- **Predicted Bloom level:** Apply (BT3)
- **Classifier confidence:** 90.07%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 1.04%; Understand: 0.72%; Apply: 90.07%; Analyze: 5.98%; Evaluate: 0.04%; Create: 2.16%

**Generator rationale (unverified):** This question requires the application of SQL concepts such as filtering with WHERE clause, grouping with GROUP BY, and using aggregate functions like SUM to derive the required result.

**Generated model answer (unverified):**

SELECT ProductID, SUM(Quantity) AS TotalQuantity FROM Sales WHERE SaleDate BETWEEN '2023-06-01' AND '2023-06-30' GROUP BY ProductID;

**Generated rubric criteria (unverified):**

- Correct use of WHERE clause for date filtering
- Proper use of GROUP BY and aggregate function
- Accurate syntax and structure of the query

### Q06 — Structured Query Language (SQL)

A database contains a table named 'Employees' with columns 'EmployeeID', 'Name', 'DepartmentID', and 'Salary'. Write an SQL query to update the salary of all employees in the 'Sales' department by 10%.

- **Marks:** 8
- **Requested/generated Bloom level:** Apply
- **Predicted Bloom level:** Apply (BT3)
- **Classifier confidence:** 81.53%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 1.87%; Understand: 0.36%; Apply: 81.53%; Analyze: 6.90%; Evaluate: 0.09%; Create: 9.26%

**Generator rationale (unverified):** This question tests the application of SQL update statements with proper use of WHERE clause to target a specific department and apply a percentage increase to the salary field.

**Generated model answer (unverified):**

UPDATE Employees SET Salary = Salary * 1.10 WHERE DepartmentID = (SELECT DepartmentID FROM Departments WHERE DepartmentName = 'Sales');

**Generated rubric criteria (unverified):**

- Correct use of UPDATE statement
- Proper use of subquery for department ID
- Accurate calculation of salary increase

### Q07 — Schema Refinement

Consider a database schema that contains a relation 'Employee' with attributes: EmpID, Name, DeptID, and Salary. Analyze how the schema could be refined to eliminate redundancy and ensure data integrity, and explain the implications of such refinement.

- **Marks:** 8
- **Requested/generated Bloom level:** Analyze
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 47.18%
- **Agreement:** Match
- **Below review threshold:** Yes
- **Class scores:** Remember: 0.13%; Understand: 9.32%; Apply: 42.15%; Analyze: 47.18%; Evaluate: 0.08%; Create: 1.13%

**Generator rationale (unverified):** This question asks the examinee to analyze a scenario and suggest schema refinement strategies, which requires understanding of normalization and its implications.

**Generated model answer (unverified):**

The schema can be refined by decomposing the 'Employee' relation into two relations: 'Employee' (EmpID, Name, DeptID) and 'Department' (DeptID, DeptName). This eliminates redundancy in department names and ensures data integrity. The implications include improved data consistency, reduced update anomalies, and better query performance.

**Generated rubric criteria (unverified):**

- Identification of redundancy and normalization principles
- Explanation of the decomposition process
- Analysis of the implications of the refined schema

### Q08 — Schema Refinement

Analyze the trade-offs between denormalization and normalization in the context of schema refinement. Provide a real-world example where denormalization might be beneficial and explain the trade-offs involved.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Analyze
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 85.78%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 0.01%; Understand: 0.59%; Apply: 13.60%; Analyze: 85.78%; Evaluate: 0.00%; Create: 0.02%

**Generator rationale (unverified):** This question requires the examinee to analyze the pros and cons of denormalization versus normalization, and to apply the concept in a practical scenario.

**Generated model answer (unverified):**

Denormalization may improve query performance in data warehouses where read operations are frequent, but it can lead to redundancy and update anomalies. For example, in a sales database, denormalizing the 'Sales' and 'Product' relations into a single 'SalesProduct' table can speed up reporting. However, this may result in duplicate product data and require more complex update operations.

**Generated rubric criteria (unverified):**

- Understanding of normalization and denormalization principles
- Ability to provide a real-world example
- Analysis of the trade-offs involved

### Q09 — Database Indexes and Storage Structures

Evaluate the trade-offs between using a B+ Tree index and a Hash index in a database system, considering factors such as query performance, storage overhead, and update operations.

- **Marks:** 8
- **Requested/generated Bloom level:** Evaluate
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 96.36%
- **Agreement:** Mismatch
- **Below review threshold:** No
- **Class scores:** Remember: 0.00%; Understand: 0.04%; Apply: 3.10%; Analyze: 96.36%; Evaluate: 0.49%; Create: 0.01%

**Generator rationale (unverified):** This question requires the candidate to critically assess the pros and cons of two different indexing structures, considering multiple performance and storage aspects.

**Generated model answer (unverified):**

A B+ Tree index is efficient for range queries and supports ordered traversal, but has higher storage overhead and slower updates. A Hash index is faster for exact match queries but inefficient for range queries and does not support ordered traversal. The choice depends on the workload and data access patterns.

**Generated rubric criteria (unverified):**

- Analysis of B+ Tree vs. Hash index trade-offs
- Consideration of query performance
- Evaluation of storage overhead
- Assessment of update operations

### Q10 — Database Indexes and Storage Structures

Evaluate how the choice of storage structure (heap file vs. sorted file) impacts the performance of a database system when dealing with frequent range queries and frequent insertions.

- **Marks:** 7
- **Requested/generated Bloom level:** Evaluate
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 94.08%
- **Agreement:** Mismatch
- **Below review threshold:** No
- **Class scores:** Remember: 0.00%; Understand: 0.01%; Apply: 5.80%; Analyze: 94.08%; Evaluate: 0.11%; Create: 0.01%

**Generator rationale (unverified):** This question requires the candidate to evaluate the impact of two different storage structures on performance for specific operations, considering both query and insertion efficiency.

**Generated model answer (unverified):**

A sorted file with a B+ Tree index supports efficient range queries and ordered data retrieval, but insertions are slower due to the need to maintain order. A heap file with a clustered index allows faster insertions but is less efficient for range queries. The choice depends on the workload and access patterns.

**Generated rubric criteria (unverified):**

- Comparison of heap file and sorted file performance
- Impact on range queries
- Impact on insertion operations
- Consideration of workload and access patterns

### Q11 — Introduction to DBMS & Conceptual Database Design

Design a conceptual model for a library management system that includes entities such as Book, Member, and Borrowing, ensuring proper relationships and attributes are defined.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Create
- **Predicted Bloom level:** Create (BT6)
- **Classifier confidence:** 99.78%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 0.00%; Understand: 0.03%; Apply: 0.13%; Analyze: 0.04%; Evaluate: 0.02%; Create: 99.78%

**Generator rationale (unverified):** This question requires students to create a conceptual model from scratch, demonstrating understanding of entities, attributes, and relationships.

**Generated model answer (unverified):**

The conceptual model should include entities like Book (attributes: ISBN, Title, Author, Publication Year), Member (attributes: Member ID, Name, Address, Contact), and Borrowing (attributes: Borrowing ID, Borrow Date, Return Date). Relationships should include 'Borrowed by' between Book and Member, and 'Borrowing' between Book and Member with cardinality as many-to-many.

**Generated rubric criteria (unverified):**

- Correct identification of entities and attributes
- Accurate representation of relationships
- Use of cardinality and participation

### Q12 — Introduction to DBMS & Conceptual Database Design

Create a conceptual data model for a university system that manages students, courses, and enrollments. Define the entities, their attributes, and relationships with appropriate cardinality.

- **Marks:** 8.5
- **Requested/generated Bloom level:** Create
- **Predicted Bloom level:** Create (BT6)
- **Classifier confidence:** 69.46%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 4.71%; Understand: 14.36%; Apply: 9.37%; Analyze: 1.96%; Evaluate: 0.14%; Create: 69.46%

**Generator rationale (unverified):** This question asks students to construct a conceptual model from scratch, ensuring they apply DBMS principles to design a realistic system.

**Generated model answer (unverified):**

The conceptual model should include entities such as Student (attributes: Student ID, Name, Email, Major), Course (attributes: Course ID, Title, Credits, Department), and Enrollment (attributes: Enrollment ID, Grade). Relationships should include 'Enrolled in' between Student and Course (many-to-many), and 'Enrolled in' between Student and Course through Enrollment (one-to-many).

**Generated rubric criteria (unverified):**

- Identification of relevant entities and attributes
- Accurate representation of relationships and cardinality
- Logical consistency of the model

### Q13 — Database Security

What are the primary functions of access control in a database system?

- **Marks:** 5
- **Requested/generated Bloom level:** Remember
- **Predicted Bloom level:** Remember (BT1)
- **Classifier confidence:** 90.41%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 90.41%; Understand: 2.17%; Apply: 2.26%; Analyze: 4.93%; Evaluate: 0.14%; Create: 0.08%

**Generator rationale (unverified):** This question tests the recall of fundamental concepts related to access control, which is a core aspect of database security.

**Generated model answer (unverified):**

The primary functions of access control in a database system include restricting unauthorized access to data, ensuring that users can only access data they are authorized to use, and maintaining the integrity and confidentiality of the data.

**Generated rubric criteria (unverified):**

- Recall of access control functions
- Clarity of explanation

### Q14 — Database Security

List three types of authentication mechanisms used in database security.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Remember
- **Predicted Bloom level:** Remember (BT1)
- **Classifier confidence:** 95.20%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 95.20%; Understand: 3.79%; Apply: 0.69%; Analyze: 0.25%; Evaluate: 0.04%; Create: 0.02%

**Generator rationale (unverified):** This question assesses the ability to recall common authentication methods, which are essential for ensuring secure access to database systems.

**Generated model answer (unverified):**

Three types of authentication mechanisms used in database security are password authentication, biometric authentication, and token-based authentication.

**Generated rubric criteria (unverified):**

- Identification of authentication types
- Accuracy of examples
- Clarity of response

### Q15 — Database Recovery and Log Management

Explain the purpose of a log file in a database system and how it contributes to database recovery.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Understand
- **Predicted Bloom level:** Understand (BT2)
- **Classifier confidence:** 77.53%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 13.42%; Understand: 77.53%; Apply: 3.28%; Analyze: 5.38%; Evaluate: 0.24%; Create: 0.13%

**Generator rationale (unverified):** This question tests the understanding of the role and importance of log files in ensuring data consistency and recoverability.

**Generated model answer (unverified):**

A log file in a database system records all changes made to the database, such as updates, deletions, and insertions. It plays a critical role in database recovery by providing a history of transactions, allowing the system to roll back to a consistent state in case of a failure. Logs are also used during recovery to reapply or undo transactions as needed.

**Generated rubric criteria (unverified):**

- Explanation of the purpose of a log file
- Description of how logs contribute to recovery
- Clarity and accuracy of the answer

### Q16 — Database Recovery and Log Management

Describe the difference between a redo log and an undo log in the context of database recovery.

- **Marks:** 8
- **Requested/generated Bloom level:** Understand
- **Predicted Bloom level:** Understand (BT2)
- **Classifier confidence:** 53.75%
- **Agreement:** Match
- **Below review threshold:** Yes
- **Class scores:** Remember: 35.74%; Understand: 53.75%; Apply: 1.47%; Analyze: 8.89%; Evaluate: 0.08%; Create: 0.07%

**Generator rationale (unverified):** This question assesses the understanding of the different types of logs and their specific roles in recovery mechanisms.

**Generated model answer (unverified):**

A redo log records all changes made to the database during a transaction, allowing the system to reapply these changes during recovery to bring the database to a consistent state. An undo log, on the other hand, records the previous state of data before a transaction was applied, enabling the system to roll back transactions in case of a failure and restore the database to a previous consistent state.

**Generated rubric criteria (unverified):**

- Correct identification of redo and undo logs
- Explanation of their roles in recovery
- Clarity and correctness of the explanation

### Q17 — Database Transaction Management and Concurrency Control

A banking application is handling multiple transactions for account transfers. Explain how you would ensure that these transactions are executed in a way that maintains consistency and isolation. Provide an example of a scenario where locking might be needed and how it would be applied.

- **Marks:** 7.5
- **Requested/generated Bloom level:** Apply
- **Predicted Bloom level:** Understand (BT2)
- **Classifier confidence:** 62.13%
- **Agreement:** Mismatch
- **Below review threshold:** No
- **Class scores:** Remember: 0.62%; Understand: 62.13%; Apply: 32.24%; Analyze: 2.51%; Evaluate: 1.93%; Create: 0.57%

**Generator rationale (unverified):** This question requires the application of concepts like isolation, consistency, and locking mechanisms in a real-world scenario, which tests the candidate's understanding of concurrency control.

**Generated model answer (unverified):**

To ensure consistency and isolation, transactions should be managed using ACID properties. Locking can be used to prevent conflicts, for example, when transferring money between accounts. A lock on the source account would prevent another transaction from modifying it until the first transaction is complete. This ensures that the account balances remain consistent and isolated from concurrent changes.

**Generated rubric criteria (unverified):**

- Application of ACID properties
- Explanation of locking mechanism
- Example scenario and its relevance

### Q18 — Database Transaction Management and Concurrency Control

You are designing a multi-user database system for an online marketplace. Describe how you would handle concurrent access to inventory items to prevent over-selling. Include the use of a specific concurrency control technique and justify your choice.

- **Marks:** 8
- **Requested/generated Bloom level:** Apply
- **Predicted Bloom level:** Apply (BT3)
- **Classifier confidence:** 62.97%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 0.31%; Understand: 29.74%; Apply: 62.97%; Analyze: 0.92%; Evaluate: 5.31%; Create: 0.76%

**Generator rationale (unverified):** This question tests the ability to apply concurrency control techniques to solve a real-world problem, such as over-selling in an online marketplace, and to justify the choice of a specific technique.

**Generated model answer (unverified):**

To prevent over-selling, I would use optimistic concurrency control. Each transaction checks if the inventory item is still available before committing. If two users attempt to purchase the same item simultaneously, the second transaction will be rolled back if the inventory has been modified by the first. This approach reduces the need for locks and improves performance in systems with low conflict rates.

**Generated rubric criteria (unverified):**

- Use of concurrency control technique
- Explanation of how it prevents over-selling
- Justification of the technique chosen

### Q19 — Java Database Connectivity (JDBC)

Compare and contrast the use of JDBC Connection objects with and without a database URL that includes a username and password. Analyze the implications of each approach on application security and connection management.

- **Marks:** 8.5
- **Requested/generated Bloom level:** Analyze
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 96.66%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 0.02%; Understand: 0.25%; Apply: 3.07%; Analyze: 96.66%; Evaluate: 0.00%; Create: 0.00%

**Generator rationale (unverified):** This question requires the examinee to analyze the differences in handling connection objects based on how credentials are provided, considering security and connection management aspects.

**Generated model answer (unverified):**

When a JDBC Connection object is created with a database URL that includes the username and password, it is less secure as credentials are exposed in the URL. In contrast, separating credentials from the URL improves security by allowing them to be managed separately, such as through environment variables or configuration files. Additionally, using connection pooling with the latter approach allows for better connection management and performance optimization.

**Generated rubric criteria (unverified):**

- Comparison of URL-based vs. separate credentials
- Analysis of security implications
- Discussion on connection management

### Q20 — Java Database Connectivity (JDBC)

Analyze the impact of using a JDBC PreparedStatement versus a Statement object on database performance and SQL injection vulnerabilities. Provide a scenario where each approach would be most appropriate.

- **Marks:** 7
- **Requested/generated Bloom level:** Analyze
- **Predicted Bloom level:** Analyze (BT4)
- **Classifier confidence:** 77.36%
- **Agreement:** Match
- **Below review threshold:** No
- **Class scores:** Remember: 0.01%; Understand: 0.05%; Apply: 22.57%; Analyze: 77.36%; Evaluate: 0.01%; Create: 0.01%

**Generator rationale (unverified):** This question requires the examinee to analyze the performance and security trade-offs of using PreparedStatement versus Statement in JDBC, and to provide practical examples of when each is suitable.

**Generated model answer (unverified):**

PreparedStatement is more efficient for repeated SQL executions and helps prevent SQL injection by automatically handling parameterized queries. Statement is suitable for one-time queries with dynamic SQL. For example, PreparedStatement is ideal for user login systems to prevent SQL injection, while Statement might be used for generating a report with a unique query that does not involve user input.

**Generated rubric criteria (unverified):**

- Analysis of performance differences
- Discussion on SQL injection prevention
- Scenario-based application of each approach

## Evidence and limitations

- Raw per-batch generator responses and requests: `docs/validation/bloom_20_2026-10-17/generation_01.json` through `generation_10.json`.
- Consolidated generated questions: `docs/validation/bloom_20_2026-10-17/generated_questions.json`.
- Complete classifier predictions, all class scores, token counts and review flags: `docs/validation/bloom_20_2026-10-17/bloom_results.json`.
- These are fresh outputs from the connected model, not the older validation set in `docs/validation/bloom_20`.
- The sample is small and its level distribution is uneven; results do not establish performance across courses or future questions.
- Uniqueness was checked only within this batch using normalized exact text. Semantic novelty and similarity to training or historical questions were not established.
- No independent lecturer ground truth was supplied. Question solvability, answer correctness, rubric quality and marks suitability have not received comprehensive independent validation; specific issues observed in Q06 and Q07 are noted above.
- All questions require lecturer review before assessment use, including high-confidence matches.
