# Reproducibility

## 5-minute reproduction
1. Clone: git clone https://github.com/sparkainlp-x/waveholo-telescope
2. Install: make install
3. Test: make test
4. Docs: make docs
5. Smoke: make smoke (expected exit code 2 with 3 seeds; claim gate requires 20 seeds)

## Evidence status
- Synthetic-only demonstration: SYNTHETIC
- Preregistered factorial benchmark: UNRUN
- Full radial-order 2-10 factorial: UNRUN (blocked)

## Claim gates
Smoke runner intentionally returns 2 when seed count does not meet the 20-seed claim gate. This is fail-closed behavior, not a bug.
