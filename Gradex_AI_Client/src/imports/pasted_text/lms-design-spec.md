Design a modern Learning Management System (LMS) web application with a clean, 
professional interface using a blue and white color scheme with green/yellow/red 
accent colors for performance indicators.

CORE PAGES TO DESIGN:

1. AUTHENTICATION PAGES
- Login page with role selection (Student/Lecturer)
- Registration page with form fields for both user types
- Forgot password page
- Clean, centered layout with subtle illustrations

2. LECTURER DASHBOARD (Main Hub)
- Top navigation bar with: Logo, Dashboard, Grading, Exam Creator, Viva Grading, 
  Profile, Logout
- Sidebar with quick stats and recent activities
- Main content area with 4 large card buttons:
  * "Grade Diagram Exams" (icon: diagram/flowchart)
  * "Grade Handwritten Exams" (icon: paper/pen)
  * "Student Analytics" (icon: chart/graph)
  * "Viva Assessment" (icon: video/camera)
- Each card should have icon, title, brief description, and "Access" button

3. GRADING INTERFACE (Diagram & Handwritten)
- Split screen layout:
  * Left: Uploaded exam preview (PDF viewer or image)
  * Right: Grading controls
- Upload area for:
  * Student exam paper (drag & drop zone)
  * Marking rubric (file upload button)
- Action buttons: "Extract & Grade", "Manual Override", "Save Draft"
- Progress indicator when AI is processing
- Results section showing: Score, Breakdown, AI Confidence Level

4. ANALYTICS DASHBOARD
Design with multiple sections in scrollable layout:

SECTION 1 - Executive Summary Cards (4 cards in a row)
- Class Performance Distribution (bar chart visualization)
- At-Risk Students Count (red alert style, shows number + list)
- Problem Questions Count (yellow warning style)
- Cognitive Gap Alerts (orange indicator with count)

SECTION 2 - Student Performance View
- Leaderboard table with columns:
  * Student ID | Avg Score | Performance Band (color-coded badge) | 
    Weak Questions | Cognitive Level
- Color coding: Green (High), Yellow (Medium), Red (Low)
- Sortable column headers with arrows
- Click-to-expand rows for detailed drill-down showing:
  * Weak questions breakdown
  * Score distribution chart (performance/concept/cognitive)
  * Individual question performance grid

SECTION 3 - Question Analysis View
- Large heatmap visualization (Students on Y-axis, Questions on X-axis)
- Color gradient from red (poor) to green (excellent)
- Below heatmap: Problem questions list with:
  * Question ID | Students Below Threshold | Avg Score | 
    Required Level vs Actual Level | Action Button
- Each problem question expandable to show model answer

SECTION 4 - Cognitive Gap Analysis
- Bloom's Taxonomy ladder chart
- Scatter plot with diagonal line showing expected vs actual performance
- Points above diagonal in green (exceeding), below in red/orange (gaps)
- Interactive tooltips on hover
- Gap severity legend (LOW/MEDIUM/HIGH)

SECTION 5 - Topic Mastery Grid
- Matrix view: Students (rows) × Topics (columns)
- Cell colors represent mastery level per topic
- Highlight struggling topics (≥40% failure rate)
- Row and column aggregates showing averages

5. EXAM CREATOR PAGE
- Year/Level selector (dropdown: 1st Year, 2nd Year, 3rd Year, 4th Year Final)
- Exam type selector (Mid-term, Final, Quiz)
- Question bank interface with:
  * Search and filter by topic, difficulty, Bloom's level
  * Drag-and-drop question builder
  * Preview pane on right side
- Generated exam preview with:
  * Total marks calculation
  * Bloom's level distribution chart
  * Topic coverage percentage
- Export buttons (PDF, Word, Print)
- Template library section showing past exam formats

6. VIVA GRADING PAGE
- Large video upload area with drag-and-drop
- Supported formats indicator (MP4, AVI, MOV)
- Recording guidelines/checklist sidebar
- Evaluation criteria checklist:
  * Communication Skills
  * Technical Knowledge
  * Problem-Solving
  * Presentation Quality
- After upload: Video player with AI analysis panel showing:
  * Transcript
  * Key moments timeline
  * Scoring breakdown
  * AI recommendations
  * Final grade input field
- Save and export report button

7. STUDENT DASHBOARD (Simpler version)
- Welcome card with student info
- Upcoming exams calendar widget
- Recent grades table
- Performance trend chart
- Resources/announcements section

DESIGN SPECIFICATIONS:
- Use modern, clean UI with plenty of white space
- Primary color: #2563EB (blue)
- Success: #10B981 (green), Warning: #F59E0B (yellow), Danger: #EF4444 (red)
- Sans-serif font (Inter or similar)
- Card-based layouts with subtle shadows
- Responsive design (show both desktop 1440px and tablet 768px views)
- Data visualizations should use: bar charts, line graphs, heatmaps, 
  scatter plots with clear legends
- Interactive states: hover, active, disabled for all buttons
- Loading states for AI processing
- Success/error notification toasts
- Modal dialogs for confirmations

Include micro-interactions indicators like:
- Upload progress bars
- Processing spinners
- Success checkmarks
- Smooth transitions between states