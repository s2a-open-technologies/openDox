class PCMWorkletProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0][0];
    if (!input) return true;

    const pcm16 = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      let s = input[i];
      s = Math.max(-1, Math.min(1, s));
      pcm16[i] = s * 32767;
    }

    this.port.postMessage(pcm16.buffer);
    return true;
  }
}

registerProcessor("pcm-worklet", PCMWorkletProcessor);
