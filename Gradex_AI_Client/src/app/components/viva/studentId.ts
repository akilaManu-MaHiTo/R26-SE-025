/** Student ID rules for the viva pages — mirrors the server (viva_sessions.py).
 * Every student ID in the system is "IT" followed by 8 digits, e.g. IT22557056. */

export const STUDENT_ID_PATTERN = /^IT\d{8}$/;
export const STUDENT_ID_HINT = "Student ID must look like IT22557056 (IT followed by 8 digits).";

/** Trim and upper-case, as the server does before validating. */
export function normalizeStudentId(value: string): string {
  return value.trim().toUpperCase();
}

export function isValidStudentId(value: string): boolean {
  return STUDENT_ID_PATTERN.test(normalizeStudentId(value));
}
