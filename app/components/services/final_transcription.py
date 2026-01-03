
# Third party
import torch
import numpy as np
import gc
from transformers.pipelines import pipeline

# Custom imports
from app.components.llm.whisper_model import WhisperModel


class Transcriber:
    def __init__(self, model: WhisperModel = WhisperModel()):
        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model.model,
            tokenizer=model.tokenizer,
            feature_extractor=model.feature_extractor,
            #torch_dtype=torch_dtype,
            device_map="auto",
            generate_kwargs={
                "language": "de",
                "task": "transcribe", 
                "temperature": 0.0,               
            }
        )

    def transcribe(self, pcm_buffer: bytes, samplerate=16000):
        """
        Transcribe Float32 buffer using Whisper
        """

        # VRAM aufräumen bevor wir starten, um Platz für Flash Attention zu schaffen
        gc.collect()
        torch.cuda.empty_cache()

        try:
            # Float32 bytes → float32 array
            audio_array = np.frombuffer(pcm_buffer, dtype=np.float32).copy()

            if audio_array.size == 0:
                return ""

            # Pipeline übernimmt das Chunking automatisch und intelligent (Sliding Window)
            result = self.pipe(
                {"array": audio_array, "sampling_rate": samplerate},
                chunk_length_s=30,
                batch_size=4,
                return_timestamps=False,
                generate_kwargs={
                    "task": "transcribe",
                    "language": "de",     # Zwingt Whisper auf Deutsch
                    "num_beams": 5        # Erhöht die Genauigkeit durch Prüfung mehrerer Pfade
                }
            )
            
            return result.get("text", "").strip()

        except Exception as e:
            print(f"[TRANSCRIBE-ERROR] {e}")
            return ""
