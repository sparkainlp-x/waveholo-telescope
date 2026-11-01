# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only

"""waveholo-telescope: WaveHolo's off-axis holography pipeline pointed
at a telescope pupil (synthetic only).

A distant star through a circular pupil with Zernike aberrations is
propagated to a sensor, recorded as an off-axis hologram, and
reconstructed. The pupil plane is found by aperture contrast and the
wavefront is compared with the injected aberration. Synthetic ground
truth throughout; no real telescope data and no instrument claim.
"""

from .analysis import focus_sweep, parabolic_peak
from .benchmark import run_benchmark, run_condition
from .claims import evaluate, headline
from .hologram import offaxis_field, record_hologram, reconstruct_field
from .metrics import (aperture_contrast, eroded_mask, phase_agreement,
                      phase_rms_error, phase_variance)
from .propagation import (CAR_DEFAULT, DX, N, WIN_DEFAULT, WL,
                          angular_spectrum)
from .pupil import pupil_field, pupil_grid, zernike_phase
from .statistics import (benjamini_hochberg, bootstrap_median_interval,
                         claim_gate, median_and_iqr, paired_bootstrap_difference,
                         power_analysis_proportion, wilson_interval)

__version__ = "0.2.0"

__all__ = [
    "angular_spectrum", "pupil_field", "pupil_grid", "zernike_phase",
    "record_hologram", "reconstruct_field", "offaxis_field",
    "focus_sweep", "parabolic_peak", "aperture_contrast", "eroded_mask",
    "phase_rms_error", "phase_agreement", "phase_variance",
    "run_benchmark", "run_condition", "evaluate", "headline",
    "benjamini_hochberg", "bootstrap_median_interval", "claim_gate",
    "median_and_iqr", "paired_bootstrap_difference",
    "power_analysis_proportion", "wilson_interval",
    "N", "DX", "WL", "CAR_DEFAULT", "WIN_DEFAULT",
]
