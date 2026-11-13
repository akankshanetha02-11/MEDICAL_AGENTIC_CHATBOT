
// Get HTML element by ID
const $ = (id) => document.getElementById(id);

// Global Variables
let history = [];
let imageData = null;
let recorder = null;
let audioChunks = [];
let cameraStream = null;
let lastAnswer = "";

// API Headers
const headers = () => {
    const h = {};
    const token = $("token").value.trim();

    if (token) {
        h.Authorization = `Bearer ${token}`;
    }

    return h;
};

// Display Chat Message
function bubble(text, kind = "bot", sources = []) {
    const el = document.createElement("article");

    el.className = kind;
    el.textContent = text;

    if (sources.length) {
        const s = document.createElement("div");

        s.className = "sources";

        s.textContent =
            "Sources: " +
            sources
                .slice(0, 8)
                .map((x) =>
                    x.type === "pdf"
                        ? `PDF page ${x.page}`
                        : x.url
                )
                .join(" | ");

        el.appendChild(s);
    }

    $("messages").appendChild(el);

    $("messages").scrollTop =
        $("messages").scrollHeight;

    return el;
}

// Check Backend Health
async function check() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();

        $("status").textContent = data.configured
            ? "● Connected"
            : "⚠ Configure API keys";

    } catch (error) {
        $("status").textContent = "● Server offline";
    }
}

check();

// Image Upload
function setImage(file) {
    if (!file) return;

    const allowedTypes = [
        "image/png",
        "image/jpeg",
        "image/webp"
    ];

    if (
        !allowedTypes.includes(file.type) ||
        file.size > 5 * 1024 * 1024
    ) {
        alert("Use PNG/JPEG/WebP under 5MB");
        return;
    }

    const reader = new FileReader();

    reader.onload = () => {
        imageData = reader.result;

        $("thumbnail").src = imageData;
        $("preview").hidden = false;
    };

    reader.readAsDataURL(file);
}

// Image Input Event
$("image").addEventListener("change", (event) => {
    setImage(event.target.files[0]);
});

// Remove Image
$("remove").onclick = () => {
    imageData = null;

    $("preview").hidden = true;
    $("thumbnail").src = "";
    $("image").value = "";
};

// Chat Form Submission
$("chatForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = $("message").value.trim();

    if (!message) return;

    const prior = history.slice(-8);

    bubble(message, "user");

    $("message").value = "";
    $("send").disabled = true;

    const pending = bubble("Thinking...");

    try {
        const response = await fetch("/api/chat", {
            method: "POST",

            headers: {
                ...headers(),
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                message: message,
                history: prior,
                image_data: imageData
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail || "Request failed"
            );
        }

        // Display AI Answer
        pending.textContent = data.answer;

        lastAnswer = data.answer;

        // Display Sources
        if (data.sources?.length) {
            const src = document.createElement("div");

            src.className = "sources";

            src.textContent =
                "Sources: " +
                data.sources
                    .slice(0, 8)
                    .map((x) =>
                        x.type === "pdf"
                            ? `PDF page ${x.page}`
                            : x.url
                    )
                    .join(" | ");

            pending.appendChild(src);
        }

        // Save Chat History
        history.push(
            {
                role: "user",
                content: message
            },
            {
                role: "assistant",
                content: data.answer
            }
        );

        // Clear Image Preview
        $("remove").click();

    } catch (error) {
        pending.textContent = "Error: " + error.message;

    } finally {
        $("send").disabled = false;

        $("messages").scrollTop =
            $("messages").scrollHeight;
    }
});

// Microphone / Voice Recording
$("mic").onclick = async () => {

    // Stop Recording
    if (recorder && recorder.state === "recording") {
        recorder.stop();

        $("mic").textContent = "🎤 Voice";
        return;
    }

    try {
        const stream =
            await navigator.mediaDevices.getUserMedia({
                audio: true
            });

        audioChunks = [];

        recorder = new MediaRecorder(stream);

        recorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        recorder.onstop = async () => {

            stream.getTracks().forEach((track) => {
                track.stop();
            });

            const blob = new Blob(audioChunks, {
                type: recorder.mimeType
            });

            const formData = new FormData();

            formData.append(
                "file",
                blob,
                "voice.webm"
            );

            $("mic").disabled = true;

            try {
                const response = await fetch("/api/transcribe", {
                    method: "POST",
                    headers: headers(),
                    body: formData
                });

                const output = await response.json();

                if (!response.ok) {
                    throw new Error(
                        output.detail || "Transcription failed"
                    );
                }

                $("message").value = output.text;

            } catch (error) {
                alert(error.message);

            } finally {
                $("mic").disabled = false;
            }
        };

        recorder.start();

        $("mic").textContent = "⏹ Stop recording";

    } catch (error) {
        alert("Microphone unavailable: " + error.message);
    }
};

// Read AI Answer Aloud
$("listen").onclick = async () => {

    if (!lastAnswer) {
        alert("Ask a question first");
        return;
    }

    $("listen").disabled = true;

    try {
        const response = await fetch("/api/speak", {
            method: "POST",

            headers: {
                ...headers(),
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                text: lastAnswer
            })
        });

        if (!response.ok) {
            throw new Error("Speech unavailable");
        }

        const audioBlob = await response.blob();

        const audioUrl =
            URL.createObjectURL(audioBlob);

        const audio = new Audio(audioUrl);

        audio.onended = () => {
            URL.revokeObjectURL(audioUrl);
        };

        audio.onerror = () => {
            URL.revokeObjectURL(audioUrl);
        };

        await audio.play();

    } catch (error) {
        alert(error.message);

    } finally {
        $("listen").disabled = false;
    }
};

// Open Camera
$("camera").onclick = async () => {

    try {
        cameraStream =
            await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: "environment"
                }
            });

        $("video").srcObject = cameraStream;

        $("video").hidden = false;
        $("cameraActions").hidden = false;

    } catch (error) {
        alert("Camera unavailable: " + error.message);
    }
};

// Close Camera
$("closeCamera").onclick = () => {

    if (cameraStream) {
        cameraStream.getTracks().forEach((track) => {
            track.stop();
        });

        cameraStream = null;
    }

    $("video").srcObject = null;

    $("video").hidden = true;
    $("cameraActions").hidden = true;
};

// Capture Camera Image
$("snap").onclick = () => {

    const video = $("video");
    const canvas = $("canvas");

    if (!video.videoWidth || !video.videoHeight) {
        alert("Camera is not ready. Try again.");
        return;
    }

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext("2d");

    context.drawImage(
        video,
        0,
        0,
        canvas.width,
        canvas.height
    );

    canvas.toBlob((blob) => {
        if (!blob) {
            alert("Unable to capture image");
            return;
        }

        const file = new File(
            [blob],
            "camera.jpg",
            {
                type: "image/jpeg"
            }
        );

        setImage(file);

    }, "image/jpeg", 0.85);

    $("closeCamera").click();
};
