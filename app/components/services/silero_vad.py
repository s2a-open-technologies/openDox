import torch
import numpy as np

class SileroVAD:
    def __init__(self, device="cpu"):
        self.model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True
        )
        self.model.to(device).eval()
        self.device = device
        self.get_speech_prob = utils[0]
        self.frame_size = 512
        self.threshold = 0.7
        self.hop_size = 160

    @torch.no_grad()
    def contains_speech(self, audio: np.ndarray, sample_rate=16000) -> bool:
        if sample_rate != 16000:
            raise ValueError("Silero VAD expects 16kHz audio")
        if audio.ndim != 1:
            return False

        # Padde Audio auf mindestens frame_size, falls zu kurz
        if len(audio) < self.frame_size:
            audio = np.pad(audio, (0, self.frame_size - len(audio)), mode="constant")

        speech_probs = []
        for i in range(0, len(audio) - self.frame_size + 1, self.hop_size):
            frame = audio[i:i + self.frame_size]
            tensor = torch.from_numpy(frame).float().to(self.device)
            prob = self.model(tensor, sample_rate).item()
            speech_probs.append(prob)

        if not speech_probs:
            return False

        max_prob = max(speech_probs)
        speech_ratio = sum(p >= self.threshold for p in speech_probs) / len(speech_probs)
        return (max_prob >= 0.8) or (speech_ratio >= 0.3)
