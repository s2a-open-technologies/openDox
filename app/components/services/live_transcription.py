from vosk import Model, KaldiRecognizer
import json

class LiveASR:
    def __init__(self, model: str = "./model/vosk-model-de-0.21", sample_rate=16000, device: str = "cpu"):
        self.sample_rate = 16000

        # Model initialisieren
        self.model = Model(model)
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        
        # Partiale Resultate
        self.recognizer.SetWords(True)

    def process(self, pcm_chunk: bytes):
        """
        Nimmt rohe PCM16 Bytes entgegen und liefert entweder:
        - partial_text (str)   → bei Zwischenerkennung
        - final_text (str)     → bei Vosk-„complete result“
        - None                 → nichts Neues
        """

        # Audio chunk annehmen
        chunk = self.recognizer.AcceptWaveform(pcm_chunk)
        

        if chunk:
            result = json.loads(self.recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                return {"text": text}
            return None

        partial = json.loads(self.recognizer.PartialResult())
        partial_text = partial.get("partial", "").strip()

        if partial_text:
            return {"partial": partial_text}

        return None
