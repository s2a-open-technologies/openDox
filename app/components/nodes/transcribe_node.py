
# Standard library

# Third party
import torch
import numpy as np
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
from transformers.pipelines import pipeline


class Transcriber:
    def __init__(self, model_id="openai/whisper-large-v3"):
        
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
        chunk_size = 1024 * 1024  # 1 MB
        num_chunks = len(pcm_buffer) // chunk_size

        for i in range(num_chunks):
            start = i * chunk_size
            end = (i + 1) * chunk_size
            audio_array = np.frombuffer(pcm_buffer[start:end], dtype=np.float32)

            if audio_array.size > 0:
                result = self.pipe({"array": audio_array, "sampling_rate": samplerate})
                print(result["text"])

                return result["text"] 
            else:
                return "None"
    