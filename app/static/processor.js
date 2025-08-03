

class AudioProcessor extends AudioWorkletProcessor {
    process(inputs) {
        const input = inputs[0]; // erster Eingang (z. B. Mikro)
        const channelData = input && input[0]; // erster Kanal

        if (channelData && channelData.length > 0) {
            const buffer = new Float32Array(channelData); // Copy
            this.port.postMessage(buffer.buffer, [buffer.buffer]); // als transferable senden
        }

        return true; // wichtig: Audio-Flow fortsetzen
    }
}

registerProcessor("audio-processor", AudioProcessor);
