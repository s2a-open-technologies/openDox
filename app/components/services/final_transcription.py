
# Third party
import torch
import numpy as np
import gc
from transformers.pipelines import pipeline

# Custom imports
from app.components.llm.whisper_model import WhisperModel


class Transcriber:
    def __init__(self, model: WhisperModel = WhisperModel()):
        
        # Whispermodell
        self.model = model.model

    def transcribe(self, input_data: bytes | str, samplerate=16000):
        """
        Transcribe Float32 buffer OR file path using Whisper
        """

        # VRAM aufräumen bevor wir starten, um Platz für Flash Attention zu schaffen
        gc.collect()
        #torch.cuda.empty_cache()

        try:
            if isinstance(input_data, str):
                # Input is file path
                # Hugging Face pipeline accepts file path directly
                audio_input = input_data
            else:
                # Input is bytes (PCM)
                # Float32 bytes → float32 array
                # faster-whisper expects a simple 1D float32 array, NOT a dictionary like HF pipelines
                audio_input = np.frombuffer(input_data, dtype=np.float32).copy()
                if audio_input.size == 0:
                   return ""

            # Pipeline übernimmt das Chunking automatisch und intelligent (Sliding Window)
            segments, info = self.model.transcribe(
                audio_input,
                language="de",
                task="transcribe",
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            text = " ".join([segment.text for segment in segments]).strip()

            return text

        except Exception as e:
            print(f"[TRANSCRIBE-ERROR] {e}")
            return ""
