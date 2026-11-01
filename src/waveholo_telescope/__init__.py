"""waveholo-telescope: WaveHolo's off-axis holography pipeline pointed
at a telescope pupil (synthetic only).

A distant star through a circular pupil with Zernike aberrations is
propagated to a sensor, recorded as an off-axis hologram, and
reconstructed: the pupil plane is found by aperture contrast, and
the wavefront at that plane is compared against the injected
aberration. Synthetic ground truth throughout; no real telescope
data, no instrument claim. See README.md, "Honest limits".
"""

from .analysis import focus_sweep, parabolic_peak
from .hologram import offaxis_field, record_hologram, reconstruct_field
from .metrics import (aperture_contrast, eroded_mask, phase_agreement,
                      phase_rms_error, phase_variance)
from .propagation import (CAR_DEFAULT, DX, N, WIN_DEFAULT, WL,
                          angular_spectrum)
from .pupil import pupil_field, pupil_grid, zernike_phase

__all__ = ["angular_spectrum", "pupil_field", "pupil_grid",
           "zernike_phase", "record_hologram", "reconstruct_field",
           "offaxis_field", "focus_sweep", "parabolic_peak",
           "aperture_contrast", "eroded_mask",
           "phase_rms_error", "phase_agreement", "phase_variance",
           "N", "DX", "WL", "CAR_DEFAULT", "WIN_DEFAULT"]
__version__ = "0.1.1"
