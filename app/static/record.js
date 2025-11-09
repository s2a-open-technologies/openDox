let mediaRecorder;
let sessionId = Date.now().toString(); // eindeutige Session ID

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('rec-start').addEventListener('click', handleRec);
    document.getElementById('rec-stop').addEventListener('click', handleStop);
});

// Record
async function handleRec() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    mediaRecorder.ondataavailable = async (e) => {
        if (e.data.size > 0) {
            const formData = new FormData();
            formData.append("file", e.data);
            formData.append("session_id", sessionId);

            try {
            await fetch(`http://localhost:5000/api/v1/record`, {
                method: "POST",
                body: formData
            });
            } catch (error) {
                console.error("Error sending chunk:", error);
        }
}
    };

    mediaRecorder.start(1000); // Alle 1000ms einen Chunk hochladen
}

// Record stop
async function handleStop() {
    mediaRecorder.stop();
    try {
        const response = await fetch("http://localhost:5000/api/v1/record_finalize", {
        method: "POST",
        headers: { "content-type": "application/json"},
        body: JSON.stringify({ "session_id": sessionId})
        });
        console.log("Record finalized:", response.ok);
    } catch (error) {
        console.error("Error finalizing record:", error);
    }
}

