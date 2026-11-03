.PHONY: test benchmark docs

CONFIG ?= benchmarks/configs/telescope_smoke.yaml
OUTPUT ?= benchmark-output

test:
	python -m unittest discover -s tests -v

benchmark:
	worldholo-benchmark --config "$(CONFIG)" --output "$(OUTPUT)"

docs:
	python -c "from pathlib import Path; required=['SCIENTIFIC_PROTOCOL.md','BENCHMARK_PROTOCOL.md','METRICS.md','REPRODUCIBILITY.md','LIMITATIONS.md','REAL_DATA_PROTOCOL.md','VALIDATION_MATRIX.md','CLAIMS.md']; missing=[x for x in required if not (Path('docs')/x).is_file()]; raise SystemExit('Missing docs: '+', '.join(missing) if missing else 0)"
