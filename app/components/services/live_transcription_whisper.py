import numpy as np
from faster_whisper import WhisperModel
from collections import deque

class WhisperLiveASR:
    def __init__(
        self, 
        model_size="large-v3-turbo", # "large-v3" für finale Transkription
        device="cuda",
        compute_type="float16",
        chunk_len_s=3,
        overlap_s=1,
        sample_rate=16000,
        language='de',
    ):
        self.sample_rate = sample_rate
        self.chunk_samples = int(chunk_len_s * sample_rate)
        self.overlap_samples = int(overlap_s * sample_rate)
        self.buffer = bytearray()
        self.last_text = ""
        self.language = language

        # Faster-Whisper Modell laden
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)



    def strip_repeated_prefix(self, prev: str, current: str) -> str:
        """Helper function to prevent repeated prefix in transcription """
        if not prev or not current:
            return current

        # Normalisierung für den Vergleich (lowercase, strip)
        prev_lower = prev.lower().strip()
        curr_lower = current.lower().strip()
        
        # Entferne Satzzeichen am Ende von prev, damit "Wort." und "Wort" matchen
        prev_clean = prev_lower.rstrip(".,!?;:")
        
        # Wir prüfen die letzten N Zeichen (großzügig, um auch ganze Sätze zu fangen)
        check_len = min(len(prev_clean), len(curr_lower), 200)
        
        # Rückwärts suchen: Finde den längsten gemeinsamen String an der Nahtstelle
        for i in range(check_len, 2, -1): # Min 3 Zeichen Overlap
            if prev_clean.endswith(curr_lower[:i]):
                # Overlap gefunden!
                # Schneide die ersten i Zeichen vom neuen Text ab
                return current.strip()[i:].lstrip()
        
        return current
        

    def _bytes_to_float(self, audio_bytes: bytes) -> np.ndarray:
        return np.frombuffer(audio_bytes, dtype=np.float32).copy()


    def process(self, pcm_chunk: bytes) -> dict[str, str] | None:
        self.buffer.extend(pcm_chunk)
        bytes_per_sample = 4 # float32
        
        required_bytes = self.chunk_samples * bytes_per_sample
        if len(self.buffer) < required_bytes:
            return None
        
        chunk = self.buffer[:required_bytes]
        
        # Sliding Window Logik
        shift_bytes = required_bytes - (self.overlap_samples * bytes_per_sample)
        self.buffer = self.buffer[shift_bytes:]
        
        audio_float32 = self._bytes_to_float(chunk)

        # Transkription mit Faster-Whisper
        # vad_filter=True ersetzt deine externe VAD-Logik effizient
        segments, info = self.model.transcribe(
            audio_float32,
            language=self.language,
            beam_size=1,            # 1 für Near-Live Speed, 5 für Final
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False # Wichtig für Chunks, sonst halluziniert er
        )

        # Segmente zusammenfügen (bei Chunks meist nur ein Segment)
        text = "".join([s.text for s in segments]).strip()
        
        if not text:
            return None

        # Deine strip_repeated_prefix Logik bleibt identisch
        cleaned_text = self.strip_repeated_prefix(self.last_text, text)
        
        if cleaned_text:
            self.last_text += (" " + cleaned_text)
            return {"text": cleaned_text}
        
        return None