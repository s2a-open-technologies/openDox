import torch
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoTokenizer,
    AutoFeatureExtractor,
)
# Transformers
from transformers import BitsAndBytesConfig 
from faster_whisper import WhisperModel as FasterWhisperModel

class WhisperModel:
    def __init__(self, model_id="large-v3-turbo", device="cuda", compute_type="float16"):
        self.device = device
        self.model_id = model_id
        
        # Faster-Whisper lädt das Modell, den Tokenizer und Feature Extractor intern
        # Falls du ein lokales CT2-konvertiertes Modell hast, gib den Pfad an.
        # Ansonsten lädt er es automatisch von Hugging Face/CTranslate2 Repos.
        self.model = FasterWhisperModel(
            model_id, 
            device=self.device, 
            compute_type=compute_type
        )   