import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { FileText, Workflow, BarChart3, Video } from "lucide-react";
import type { AIModel } from "./components/AIBrand";
import { GradingPage } from "./components/GradingPage";
import { DiagramGrading } from "./components/DiagramGrading";
import { DiagramReconstructionPage } from "./components/DiagramReconstructionPage";
import { DiagramGuidelinePage } from "./components/DiagramGuidelinePage";
import AnalyticsPage from "./components/AnalyticsPage";
import { ExamCreator } from "./components/ExamCreator";
import { VivaPage } from "./components/VivaPage";
import { SubjectContentPage } from "./components/SubjectContentPage";
import { LiveCopilotPage } from "./components/viva-copilot/LiveCopilotPage";

export type AgentId = "diagram-evaluation" | "grading" | "question-exam" | "viva-evaluation";

export interface AgentFeature {
  path: string;
  label: string;
  title: string;
  subtitle?: string;
  element: ReactNode;
}

export interface AgentConfig {
  id: AgentId;
  basePath: string;
  name: string;
  description: string;
  icon: LucideIcon;
  model: AIModel;
  features: AgentFeature[];
}

export const AGENT_CONFIG: AgentConfig[] = [
  {
    id: "diagram-evaluation",
    basePath: "/diagram-evaluation",
    name: "Diagram Evaluation",
    description: "Auto-extract shapes, labels and structure to grade ER diagrams, flowcharts and UML submissions.",
    icon: Workflow,
    model: "structr",
    features: [
      {
        path: "/diagram-evaluation/diagram-guideline",
        label: "Diagram Guideline",
        title: "Diagram Guideline",
        subtitle: "Turn a marking scheme into the criteria used to grade diagrams",
        element: <DiagramGuidelinePage />,
      },
      {
        path: "/diagram-evaluation/diagram-grading",
        label: "Diagram Grading",
        title: "Diagram Grading",
        subtitle: "AI-assisted assessment of structured diagrams",
        element: <DiagramGrading mode="diagram" />,
      },
      {
        path: "/diagram-evaluation/diagram-reconstruction",
        label: "Diagram Reconstruction",
        title: "Diagram Reconstruction",
        subtitle: "Recreate saved ER structure from server details",
        element: <DiagramReconstructionPage />,
      },
    ],
  },
  {
    id: "grading",
    basePath: "/grading",
    name: "Grading Engine",
    description: "OCR + rubric matching for scanned handwritten answer sheets with AI confidence scoring.",
    icon: FileText,
    model: "lexo",
    features: [
      {
        path: "/grading/handwritten-grading",
        label: "Handwritten Grading",
        title: "Handwritten Grading",
        subtitle: "OCR + rubric matching for scanned papers",
        element: <GradingPage mode="handwritten" />,
      },
    ],
  },
  {
    id: "question-exam",
    basePath: "/question-exam",
    name: "Question & Exam Prediction",
    description: "Predict performance, surface cognitive gaps and compose balanced, level-appropriate exams.",
    icon: BarChart3,
    model: "pulse",
    features: [
      {
        path: "/question-exam/analytics",
        label: "Student Analytics",
        title: "Student Analytics",
        subtitle: "Class, cohort and individual insights",
        element: <AnalyticsPage />,
      },
      {
        path: "/question-exam/exam-creator",
        label: "Exam Creator",
        title: "Exam Creator",
        subtitle: "Compose balanced, level-appropriate exams",
        element: <ExamCreator />,
      },
    ],
  },
  {
    id: "viva-evaluation",
    basePath: "/viva-evaluation",
    name: "Viva Evaluation",
    description: "Upload viva recordings and get transcripts, key moments and rubric-based scoring.",
    icon: Video,
    model: "voca",
    features: [
      {
        path: "/viva-evaluation/subject-content",
        label: "Subject Content",
        title: "Subject Content",
        subtitle: "Turn lecture material into a concept rubric for technical vivas",
        element: <SubjectContentPage />,
      },
      {
        path: "/viva-evaluation/viva-assessment",
        label: "Viva Assessment",
        title: "Viva Assessment",
        subtitle: "AI-aided viva voce evaluation",
        element: <VivaPage />,
      },
      {
        path: "/viva-evaluation/live-copilot",
        label: "Live Viva",
        title: "Live Viva",
        subtitle: "Follow-up questions from the live student presentation and viva",
        element: <LiveCopilotPage />,
      },
    ],
  },
];

const PATH_TITLES: Record<string, { title: string; subtitle?: string }> = {
  "/dashboard": { title: "Dashboard", subtitle: "Your AI-powered command center" },
  "/student-dashboard": { title: "My Dashboard", subtitle: "Track your progress and upcoming work" },
};

for (const agent of AGENT_CONFIG) {
  PATH_TITLES[agent.basePath] = { title: agent.name, subtitle: agent.description };
  for (const feature of agent.features) {
    PATH_TITLES[feature.path] = { title: feature.title, subtitle: feature.subtitle };
  }
}

export function titleFor(pathname: string): { title: string; subtitle?: string } {
  return PATH_TITLES[pathname] ?? { title: "GradeX AI", subtitle: "Learning Suite" };
}
