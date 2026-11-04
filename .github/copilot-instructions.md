# Copilot Instructions

Evidence-first coding assistant. Never invent results, metrics, or unsupported claims.

## Principles
1. Evidence-first: unrun benchmarks are UNRUN, never a number.
2. Fail-closed: gate failures are design successes, not bugs.
3. Distinguish SYNTHETIC / REPORTED / TARGET / UNRUN.
4. Every benchmark output includes seed, timestamp, version, checksum.
5. Accessibility by default.
6. Never bypass claim gates or seed gates.
7. Human override for irreversible actions.

## PR checklist
- Purpose
- Scientific impact
- Evidence status (before/after)
- Tests added and run
- Metrics affected
- Limitations
- No unsupported scientific or product claim introduced
