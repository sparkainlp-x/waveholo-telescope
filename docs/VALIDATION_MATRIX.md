# Validation matrix

| Capability | Evidence type | Status | Metric | Protocol | Limitation |
|---|---|---|---|---|---|
| Synthetic hologram generation | Unit/integration test | Demonstrated for demo geometry | Shape, dtype, deterministic check | Existing tests; PROTOCOL-v1.0.0 extension UNRUN | Synthetic only |
| Reconstruction | Benchmark | Demonstrated for existing demo; factorial target UNRUN | RMSE, PSNR, SSIM | PROTOCOL-v1.0.0 | Algorithm-dependent |
| Relative focus estimation | Benchmark | Demonstrated in one historical synthetic demo; factorial target UNRUN | Focus error | PROTOCOL-v1.0.0 | Synthetic; flat peak |
| Real-data trend check | REPORTED | UNRUN | Not defined | Not defined | No telescope measurements |
| Zernike recovery | Benchmark | Partial low-order phase comparison; complete fit UNRUN | Coefficient RMSE, residual RMS WFE | PROTOCOL-v1.0.0 | Basis incomplete |
| Telescope focus recovery | Benchmark | Historical synthetic demonstration; required factorial UNRUN | Focus error | PROTOCOL-v1.0.0 | Synthetic only |
| Operational telescope validation | External measurement | UNRUN | Not defined yet | Not defined | No real data |
