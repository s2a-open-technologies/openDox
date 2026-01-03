import torch
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoTokenizer,
    AutoFeatureExtractor,
)
from transformers import BitsAndBytesConfig 


class WhisperModel:
    
    def __init__(self, model_id="openai/whisper-large-v3", cache_dir="./models_cache"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model_id= model_id
        self.cache_dir = cache_dir
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_id, cache_dir=self.cache_dir)
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(self.model_id, cache_dir=self.cache_dir)

        # Quantization
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
        )

        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id, 
            torch_dtype=self.torch_dtype,
            quantization_config=quantization_config,
            device_map="auto",
            cache_dir=self.cache_dir,
            attn_implementation="flash_attention_2"
        )