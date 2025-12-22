import torch
import numpy as np
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoTokenizer,
    AutoFeatureExtractor,
)
from transformers.pipelines import pipeline


class Transcriber:
    def __init__(self, model_id="openai/whisper-large-v3"):
        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(model_id)
        feature_extractor = AutoFeatureExtractor.from_pretrained(model_id)

        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id, 
            torch_dtype=torch_dtype
        )

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=tokenizer,
            feature_extractor=feature_extractor,
            torch_dtype=torch_dtype,
            device=device,
        )

    def transcribe(self, pcm_buffer: bytes, samplerate=16000):
        """
        Transcribe PCM16 buffer using Whisper
        """

        try:
            # PCM16 → float32 normalized
            audio_array = (
                np.frombuffer(pcm_buffer, dtype=np.int16)
                .astype(np.float32)
                / 32768.0
            )

            if audio_array.size == 0:
                return ""

            chunk_size = 30 * samplerate

            if len(audio_array) <= chunk_size:
                result = self.pipe(
                    {"array": audio_array, "sampling_rate": samplerate}
                )
                return result.get("text", "")

            # Multi-chunk processing
            results = []
            for i in range(0, len(audio_array), chunk_size):
                chunk = audio_array[i:i + chunk_size]
                if chunk.size == 0:
                    continue

                result = self.pipe(
                    {"array": chunk, "sampling_rate": samplerate}
                )
                text = result.get("text", "")
                if text:
                    results.append(text)

            return " ".join(results)

        except Exception as e:
            print(f"[TRANSCRIBE-ERROR] {e}")
            return ""
