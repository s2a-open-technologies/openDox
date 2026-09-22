"""openDox - Medical transcription platform
Copyright (C) 2025  Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

# Third party
import numpy as np

# Proven heuristic, previously only applied to the live ASR path — boost
# quiet audio so Whisper doesn't hallucinate filler phrases instead of
# returning silence.
QUIET_PEAK_THRESHOLD = 0.05
NORMALIZED_TARGET_PEAK = 0.8


def normalize_quiet_pcm(
    pcm: np.ndarray,
    peak_threshold: float = QUIET_PEAK_THRESHOLD,
    target_peak: float = NORMALIZED_TARGET_PEAK,
) -> np.ndarray:
    """Boost the gain of quiet float32 PCM audio.

    Args:
        pcm: Float32 PCM samples in the range [-1.0, 1.0].
        peak_threshold: Peak amplitude below which boosting is applied.
        target_peak: Target peak amplitude after boosting.

    Returns:
        A (possibly rescaled) float32 ndarray. No-op for silence
        (peak == 0) and for audio that is already loud enough.
    """
    peak = np.abs(pcm).max() if pcm.size else 0.0
    if 0 < peak < peak_threshold:
        return (pcm / peak * target_peak).astype(np.float32)
    return pcm
