
let ws = null;
let audioContext, micStream, workletNode;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('rec-start').addEventListener('click', handleRec);
    document.getElementById('rec-stop').addEventListener('click', handleStop);
});


// Record
async function handleRec() {
    // initialize variable;
    ws = new WebSocket(`ws://localhost:5000/api/v1/record?sid=${Date.now()}`)
    
    // initalize mediarecorder
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule("/static/processor.js")

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    console.log("Stream erhalten: ", micStream)
    const source = audioContext.createMediaStreamSource(micStream);

    let pcmBuffer = [];

    workletNode = new AudioWorkletNode(audioContext, "audio-processor");
    workletNode.port.onmessage = (event) => {
        pcmBuffer.push(...new Float32Array(event.data));
        if (pcmBuffer.length >= 16000) {  // 1 Sekunde bei 16kHz
            const buffer = new Float32Array(pcmBuffer.splice(0, 16000));
            ws.send(buffer.buffer);
        }
    };

    source.connect(workletNode).connect(audioContext.destination);
}


// Record stop
async function handleStop() {
    if (workletNode) workletNode.disconnect();
    if (audioContext) audioContext.close();
    if (micStream) micStream.getTracks().forEach(t => t.stop());
    if (ws) ws.close();
}

