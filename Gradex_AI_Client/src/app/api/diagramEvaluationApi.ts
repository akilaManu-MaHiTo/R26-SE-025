const DEFAULT_API_BASE_URL =
	(import.meta as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ??
	"http://127.0.0.1:8000";

type DiagramDetection = {
	id: string | number;
	label: string;
	bbox: [number, number, number, number];
	confidence?: number;
	text?: string;
};

type DiagramStructure = {
	entities?: Record<string, { attributes?: string[] }>;
	relationships?: Array<{
		name: string;
		entities?: string[];
		attributes?: string[];
	}>;
	unmatched_connections?: Array<{
		from: string;
		to: string;
		line: [number, number, number, number];
	}>;
};

export type DiagramApiResponse = {
	status?: string;
	detections?: DiagramDetection[];
	connections?: Array<Record<string, unknown>>;
	structure?: DiagramStructure;
	ocr?: Array<Record<string, unknown>>;
	ocr_error?: string;
	save_dir?: string;
};

export type DiagramEvaluationSaveInput = {
	result: DiagramApiResponse;
	course?: { code: string; name?: string } | null;
	studentId?: string;
	subjectCode?: string;
	subjectName?: string;
	year?: string | number;
	month?: string | number;
	semester?: string | number;
	sessionName?: string;
	diagramMarks?: number;
	remarks?: string;
};

export type DiagramEvaluationRecord = {
	student_id: string;
	subject_code: string;
	subject_name: string;
	year: number;
	month: number;
	semester: number;
	session_name: string;
	diagram_marks: number;
	diagram_details: {
		label_count: number;
		entity_count: number;
		relationship_count: number;
		detections: Array<{
			id: string;
			label: string;
			bbox: [number, number, number, number];
			confidence?: number;
			text?: string;
		}>;
		entities: Array<{ entity_name: string; attributes: string[] }>;
		relationships: Array<{
			relation_name: string;
			entities: string[];
			attributes: string[];
		}>;
		ocr_error?: string;
		structure: DiagramStructure;
	};
	diagram_entity_relations: Array<{
		entity_name: string;
		attributes: string[];
	}>;
	diagram_relations: Array<{
		relation_name: string;
		entities: string[];
		attributes: string[];
	}>;
	remarks: string;
	evaluation_result: DiagramApiResponse;
	created_at: string;
	updated_at: string;
};

export type DiagramEvaluationSaveResponse = {
	status?: string;
	inserted_id?: string;
	record?: DiagramEvaluationRecord;
};

function readJsonResponse(response: Response): Promise<unknown> {
	return response.text().then((text) => {
		if (!text.trim()) return {};
		try {
			return JSON.parse(text);
		} catch {
			return { detail: text.slice(0, 200) };
		}
	});
}

function parseApiError(data: unknown, fallback: string): string {
	if (data == null || typeof data !== "object") return fallback;
	const detail = (data as { detail?: unknown }).detail;
	if (typeof detail === "string") return detail;
	if (Array.isArray(detail)) {
		const parts = detail.map((item) => {
			if (item && typeof item === "object" && "msg" in item) {
				return String((item as { msg: string }).msg);
			}
			return String(item);
		});
		return parts.length ? parts.join("; ") : fallback;
	}
	return fallback;
}

function toTrimmedString(value: unknown, fallback = ""): string {
	if (typeof value !== "string") return fallback;
	const trimmed = value.trim();
	return trimmed || fallback;
}

function toInteger(value: unknown, fallback: number): number {
	if (typeof value === "number" && Number.isFinite(value)) {
		return Math.trunc(value);
	}

	if (typeof value === "string") {
		const parsed = Number.parseInt(value, 10);
		if (Number.isFinite(parsed)) return parsed;
	}

	return fallback;
}

function normalizeSemester(value: unknown): number {
	if (typeof value === "string") {
		const normalized = value.trim().toLowerCase();
		if (normalized === "first" || normalized === "1") return 1;
		if (normalized === "second" || normalized === "2") return 2;
	}

	return toInteger(value, 1) || 1;
}

function normalizeSessionName(value: unknown): string {
	const normalized = toTrimmedString(value);
	if (!normalized) return "Final Examination";

	if (normalized.toLowerCase() === "mid-term" || normalized.toLowerCase() === "mid term") {
		return "Mid Term";
	}

	if (normalized.toLowerCase() === "final" || normalized.toLowerCase() === "final examination") {
		return "Final Examination";
	}

	return normalized;
}

function normalizeDetections(result: DiagramApiResponse): DiagramEvaluationRecord["diagram_details"]["detections"] {
	return (result.detections ?? []).map((detection) => ({
		id: String(detection.id),
		label: toTrimmedString(detection.label, "Unknown"),
		bbox: detection.bbox,
		confidence: detection.confidence,
		text: detection.text,
	}));
}

function normalizeEntityRelations(result: DiagramApiResponse): DiagramEvaluationRecord["diagram_entity_relations"] {
	const entities = result.structure?.entities ?? {};

	return Object.entries(entities).map(([entityName, entityValue]) => ({
		entity_name: entityName,
		attributes: entityValue.attributes ?? [],
	}));
}

function normalizeDiagramRelations(result: DiagramApiResponse): DiagramEvaluationRecord["diagram_relations"] {
	return (result.structure?.relationships ?? []).map((relationship) => ({
		relation_name: relationship.name,
		entities: relationship.entities ?? [],
		attributes: relationship.attributes ?? [],
	}));
}

export function buildDiagramEvaluationSavePayload({
	result,
	course,
	studentId,
	subjectCode,
	subjectName,
	year,
	month,
	semester,
	sessionName,
	diagramMarks,
	remarks,
}: DiagramEvaluationSaveInput): DiagramEvaluationRecord {
	const detections = normalizeDetections(result);
	const diagramEntityRelations = normalizeEntityRelations(result);
	const diagramRelations = normalizeDiagramRelations(result);
	const currentDate = new Date();
	const sanitizedResult: DiagramApiResponse = { ...result };
	const resolvedSubjectCode = toTrimmedString(subjectCode, course?.code ?? "");
	const resolvedSubjectName = toTrimmedString(
		subjectName,
		course?.name ?? "",
	);

	return {
		student_id: toTrimmedString(studentId, "UNKNOWN"),
		subject_code: resolvedSubjectCode,
		subject_name: resolvedSubjectName,
		year: toInteger(year, currentDate.getFullYear()),
		month: toInteger(month, currentDate.getMonth() + 1),
		semester: normalizeSemester(semester),
		session_name: normalizeSessionName(sessionName),
		diagram_marks: toInteger(diagramMarks, detections.length),
		diagram_details: {
			label_count: detections.length,
			entity_count: diagramEntityRelations.length,
			relationship_count: diagramRelations.length,
			detections,
			entities: diagramEntityRelations,
			relationships: diagramRelations,
			ocr_error: result.ocr_error,
			structure: result.structure ?? {},
		},
		diagram_entity_relations: diagramEntityRelations,
		diagram_relations: diagramRelations,
		remarks: toTrimmedString(remarks, result.ocr_error ?? ""),
		evaluation_result: sanitizedResult,
		created_at: currentDate.toISOString(),
		updated_at: currentDate.toISOString(),
	};
}

export async function saveDiagramEvaluation(
	payload: DiagramEvaluationRecord,
	apiBaseUrl: string = DEFAULT_API_BASE_URL,
): Promise<DiagramEvaluationSaveResponse> {
	const response = await fetch(`${apiBaseUrl}/api/diagram-evaluate-save`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
		},
		body: JSON.stringify(payload),
	});

	const data = (await readJsonResponse(response)) as DiagramEvaluationSaveResponse;

	if (!response.ok) {
		throw new Error(parseApiError(data, "Failed to save diagram evaluation."));
	}

	return data;
}
