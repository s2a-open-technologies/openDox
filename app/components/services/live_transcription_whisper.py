from transformers import pipeline
import numpy as np
import torch
from collections import deque
from .silero_vad import SileroVAD
from transformers import WhisperProcessor
class WhisperLiveASR:
    
    def __init__(
        self, 
        model_name="openai/whisper-small",
        device="cuda",
        chunk_len_s=3,    # Three second chunks
        overlap_s=1.5,      # Half of the time overlap
        sample_rate=16000,
        language='de'
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
        
        # Whisper Processor
        self.whisper_processor = WhisperProcessor.from_pretrained(model_name)
        self.last_prompt_ids = None
        
        # Whipser Pipeline with GPU        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=model_name,
            device=device,
            torch_dtype=torch.float16,
            return_timestamps=False,
            generate_kwargs={
                "language": language,
                "task": "transcribe", 
                "temperature": 0.0,
                "max_new_tokens": 32,         
                "compression_ratio_threshold": 2.0,
                "length_penalty": 1,
                "repetition_penalty": 1, 
                "logprob_threshold": -1.0,  
                "no_speech_threshold": 0.6,
                "no_repeat_ngram_size": 3
            }
        )
        
        
    def _bytes_to_float(self, audio_bytes: bytes) -> np.ndarray:
        """PCM16 Bytes to float32 array"""
        return np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    
    
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

        prev_words = prev.split()
        curr_words = current.split()

        i = 0
        while i < min(len(prev_words), len(curr_words)) and prev_words[i] == curr_words[i]:
            i += 1

        return " ".join(curr_words[i:])

    
        
    def process(self, pcm_chunk: bytes) -> dict[str, str] | None:
        """
        Processes a PCM16 chunk and returns the transcription result.
        
        Returns:
            {"text": str } if success else None
        """
        
        self.buffer.extend(pcm_chunk)
        
        # Wait for data
        required_bytes = self.chunk_samples *2
        if len(self.buffer) < required_bytes:
            return None
        
        # Extract chunk with overlap
        chunk = self.buffer[:self.chunk_samples * 2]
        self.buffer=self.buffer[required_bytes - self.overlap_samples * 2:]
        
        # Convert and process
        audio_float32 = self._bytes_to_float(chunk)
        
        if audio_float32.ndim != 1:
            raise ValueError(f"Audio must be 1D sein, got shape {audio_float32.shape}")

        print(f"Audio shape: {audio_float32.shape}, dtype: {audio_float32.dtype}")
        print(f"Min/Max: {audio_float32.min():.3f}, {audio_float32.max():.3f}")        
       
        # Checks for VAD
        if not self.vad.contains_speech(audio=audio_float32):
            self.last_prompt_ids = None
            print("No speech detected, skipping transcription.")
            return None
        
        print(f"Sprache erkannt! Min/Max: {audio_float32.min():.3f}/{audio_float32.max():.3f}")
        
        # Apply gain to the chunk
        audio_float32 = self._apply_gain(audio_float32)
        

        try:

            current_generated_kwargs = {}
            
            if self.last_prompt_ids is not None:
                current_generated_kwargs['decoder_input_ids'] = torch.tensor([self.last_prompt_ids]).to(self.pipe.device)
           
            # Transcription
            result = self.pipe(
                {"array": audio_float32, "sampling_rate": self.sample_rate},
                chunk_length_s=self.chunk_len_s,
                batch_size=1,
                generate_kwargs=current_generated_kwargs,
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
            
            # Just the last 10 Tokens
            prompt_text = " ".join(cleaned_text.split()[-10:])
            
            # Get the IDs of the text
            text_prompt_ids_raw = self.whisper_processor.get_prompt_ids(
                prompt_text,
                return_tensors="pt"
            )[0].tolist()
            
            print("[TEXT-PROMPT-IDS]: ", text_prompt_ids_raw)
        
            forced_ids_raw = self.whisper_processor.get_decoder_prompt_ids(
                language="de", task="transcribe", no_timestamps=True
            )
            
            print("[FORCED_IDS_RAW]: ", forced_ids_raw)
            
            forced_ids = [token_id for (token_index, token_id) in forced_ids_raw]
            
            if isinstance(text_prompt_ids_raw, int):
                text_prompt_ids = [text_prompt_ids_raw]
            elif isinstance(text_prompt_ids_raw, list):
                text_prompt_ids = text_prompt_ids_raw
            else:
                # Letzte Rettung: Erzwinge List-Typ
                text_prompt_ids = list(text_prompt_ids_raw)
            
            self.last_prompt_ids = forced_ids + text_prompt_ids
            print("[LAST_PROMPT_IDS]: ", self.last_prompt_ids)
        

            return {"text": cleaned_text}
            
        except Exception as e:
            print(f"[ASR-ERROR] {e}")
            return None
        
        
        
        