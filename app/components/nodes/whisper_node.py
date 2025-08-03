
# Standard library

# Third party
import torch
import numpy as np
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


class Transcriber:
    def __init__(self, model_id="openai/whisper-tiny"):
        # Paremeters for running
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        # Processor
        processor=AutoProcessor.from_pretrained(model_id)

        # Pipeline
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=AutoModelForSpeechSeq2Seq.from_pretrained(model_id, torch_dtype=torch_dtype),
            processor=processor,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            torch_dtype=torch_dtype,
            device=device
        )
    
    def transcribe(self, pcm_buffer: bytes, samplerate=16000):
        """Function to transcribe the cunks in realtime"""
        
        # Convert to numpy array
        audio_array = np.frombuffer(pcm_buffer, dtype=np.float32)   
        
        if audio_array.size == 0:
            return ""  
        
        # Processing
        result = self.pipe({"array": audio_array, "sampling_rate": samplerate})
        print(result["text"])
        
        # Returns the result
        return result["text"]
    