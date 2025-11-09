import { useState, useRef } from "react";
import RecordButton from "./recordButton";

export default function RecordView () {
    const [recording, setRecording] = useState(false);
    const mediaRecorderRef = useRef(null);

    const chunks = useRef([]);

    const startRecording = async () => {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

        const recorder = new MediaRecorder(stream, {
            mimeType: "audio/webm"
        });

        recorder.ondataavailable = async (e) => {
            if (e.data.size === 0) return;

            const formData = new FormData();
            formData.append("chunk", e.data, `chunk-${Date.now()}.webm`)

            fetch("api/v1/record", {
                method: "POST",
                body: formData
            });
        };

        // Chunking every 10 seconds
        recorder.start(10000)

        mediaRecorderRef.current = recorder;
        setRecording(true);
    };

    const stopRecording = () => {
        mediaRecorderRef.current.stop();
        setRecording(false);2
    }

    const toggleRecording = () => {
        if (recording) stopRecording();
        else startRecording();
    }

    return (
        <RecordButton
            recording={recording}
            onToggle={toggleRecording}
        />
    )
    
}