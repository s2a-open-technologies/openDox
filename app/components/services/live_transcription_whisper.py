from transformers import pipeline
import numpy as np
import torch
import gc
from collections import deque
from .silero_vad import SileroVAD
from transformers import BitsAndBytesConfig

from app.components.llm.whisper_model import WhisperModel

class WhisperLiveASR:
    
    def __init__(
        self, 
        model: WhisperModel = WhisperModel(),
        device="cuda",
        chunk_len_s=3,
        overlap_s=1,
        sample_rate=16000,
        language='de',
        ):
        """
        This class provides a live audio transcription service using the Whisper model from OpenAI.
        It processes incoming audio data in chunks and performs real-time speech recognition.

        Parameters:
        - model_name: The name of the Whisper model to use. Default is "openai/whisper-small".
        - device: The device to run the model on, either "cpu" or "cuda". Default is "cuda".
        - chunk_len_s: The length of each audio chunk in seconds. Default is 3.0.
        - overlap_s: The amount of overlap between consecutive chunks in seconds. Default is 1.5.
        - sample_rate: The sample rate of the input audio data. Default is 16000 Hz.
        - language: The language of the input audio data. Default is "german".
        """
        
        self.sample_rate = sample_rate
        self.chunk_len_s = chunk_len_s
        self.overlap_s = overlap_s
                
        self.chunk_samples = int(chunk_len_s * sample_rate)
        self.overlap_samples = int(overlap_s * sample_rate)
        self.buffer = bytearray()
        self.audio_history = deque(maxlen=3)    # letzte 3 Chunks für Kontext
        
        self.last_text = ""
        
        # VAD Voice detection
        self.vad = SileroVAD(device=device)
        
        
        # Whipser Pipeline with GPU        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model.model,
            tokenizer=model.tokenizer,
            feature_extractor=model.feature_extractor,
            return_timestamps=False,
            generate_kwargs={
                "language": language,
                "task": "transcribe", 
                "temperature": 0.0,
                "max_new_tokens": 32,         
                "compression_ratio_threshold": 2.0,
                "condition_on_prev_tokens": False,
                "length_penalty": 1,
                "repetition_penalty": 1.2,  # WICHTIG: > 1.0 bestraft Wiederholungen, < 1.0 fördert sie!
                "logprob_threshold": -1.0,  
                "no_speech_threshold": 0.8, # Etwas strenger, um "Murks" bei Stille zu vermeiden
                "no_repeat_ngram_size": 3
            }
        )
        
        
    def _bytes_to_float(self, audio_bytes: bytes) -> np.ndarray:
        """Float32 Bytes to float32 array (Direct copy)"""
        return np.frombuffer(audio_bytes, dtype=np.float32).copy()
    
    
    def _apply_gain(self, audio_float32: np.ndarray, target_rms=0.1) -> np.ndarray:
        """Automatic Gain Control (AGC): Normalisiert die Lautstärke."""
        rms = np.sqrt(np.mean(audio_float32**2))
        if rms > 0:
            audio_float32 *= min(target_rms / rms, 3.0)  # max 3x boost
        return np.clip(audio_float32, -0.95, 0.95)  
    
    
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

    
        
    def process(self, pcm_chunk: bytes) -> dict[str, str] | None:
        """
        Processes a PCM16 chunk and returns the transcription result.
        
        Returns:
            {"text": str } if success else None
        """
        
        self.buffer.extend(pcm_chunk)
        
        # Float32 hat 4 Bytes pro Sample (statt 2 bei Int16)
        bytes_per_sample = 4 
        
        # Wait for data
        required_bytes = self.chunk_samples * bytes_per_sample
        if len(self.buffer) < required_bytes:
            return None
        
        # Extract chunk with overlap
        chunk = self.buffer[:self.chunk_samples * bytes_per_sample]
        
        # Sliding Window: Entferne den verarbeiteten Teil, behalte den Overlap
        shift_bytes = required_bytes - (self.overlap_samples * bytes_per_sample)
        self.buffer = self.buffer[shift_bytes:]
        
        # Convert and process
        audio_float32 = self._bytes_to_float(chunk)
        
        if audio_float32.ndim != 1:
            raise ValueError(f"Audio must be 1D sein, got shape {audio_float32.shape}")

        print(f"Audio shape: {audio_float32.shape}, dtype: {audio_float32.dtype}")
        print(f"Min/Max: {audio_float32.min():.3f}, {audio_float32.max():.3f}")        
       
        # Checks for VAD
        if not self.vad.contains_speech(audio=audio_float32):
            print("No speech detected, skipping transcription.")
            return None
        
        print(f"Sprache erkannt! Min/Max: {audio_float32.min():.3f}/{audio_float32.max():.3f}")
        
        # Apply gain to the chunk
        audio_float32 = self._apply_gain(audio_float32)
        

        try:
          
            # Transcription
            result = self.pipe(
                {"array": audio_float32, "sampling_rate": self.sample_rate},
                chunk_length_s=self.chunk_len_s,
                batch_size=1,
            )
            text = result["text"].strip()
            
            # Send Text to prompt for the next chunk
            if not text:                
                return None
            
            # Clean Text
            cleaned_text = self.strip_repeated_prefix(self.last_text, text)
            
            if not cleaned_text:
                return None
            
            # Add cleaned part
            self.last_text += (" " + cleaned_text)        

            return {"text": cleaned_text}
            
        except Exception as e:
            print(f"[ASR-ERROR] {e}")
            return None
        
    def close(self):
        """Explicit cleanup to free VRAM"""
        if hasattr(self, 'pipe'):
            del self.pipe
        if hasattr(self, 'vad'):
            del self.vad
        gc.collect()
        torch.cuda.empty_cache()   