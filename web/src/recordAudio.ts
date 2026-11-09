export async function recordAudio(
  signal: AbortSignal,
  onStarted: (stop: () => void) => void,
): Promise<Blob> {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    throw new Error("Microphone recording is unavailable in this browser.");
  }

  const mimeType = [
    "audio/mp4",
    "audio/webm;codecs=opus",
    "audio/webm",
  ].find((type) => MediaRecorder.isTypeSupported(type));

  if (!mimeType) {
    throw new Error("This browser has no supported recording format.");
  }

  const context = new AudioContext();
  let stream: MediaStream | undefined;
  let recorder: MediaRecorder | undefined;
  let timer: number | undefined;
  let abortRecording: (() => void) | undefined;

  try {
    await context.resume();

    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    signal.throwIfAborted();

    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    source.connect(analyser);

    const samples = new Float32Array(analyser.fftSize);
    const chunks: Blob[] = [];

    recorder = new MediaRecorder(stream, { mimeType });
    const currentRecorder = recorder;

    return await new Promise<Blob>((resolve, reject) => {
      const started = performance.now();
      let speechStarted = 0;
      let lastSpeech = 0;
      let loudFrames = 0;

      const stop = () => {
        if (currentRecorder.state === "recording") {
          currentRecorder.stop();
        }
      };

      abortRecording = () => {
        reject(new DOMException("Recording cancelled.", "AbortError"));
        stop();
      };

      signal.addEventListener("abort", abortRecording, { once: true });

      currentRecorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };

      currentRecorder.onerror = () => {
        reject(new Error("Microphone recording failed."));
      };

      currentRecorder.onstop = () => {
        if (!speechStarted) {
          reject(new Error("No speech detected. Please try again."));
          return;
        }

        const blob = new Blob(chunks, {
          type: currentRecorder.mimeType,
        });

        if (!blob.size) {
          reject(new Error("The recording was empty."));
          return;
        }

        resolve(blob);
      };

      currentRecorder.start();
      onStarted(stop);

      timer = window.setInterval(() => {
        const now = performance.now();

        analyser.getFloatTimeDomainData(samples);

        let total = 0;
        for (const sample of samples) total += sample * sample;

        const rms = Math.sqrt(total / samples.length);
        const loud = rms >= 0.01;

        loudFrames = loud ? loudFrames + 1 : 0;

        if (!speechStarted && loudFrames >= 2) {
          speechStarted = now;
        }

        if (speechStarted && loud) {
          lastSpeech = now;
        }

        const noSpeech = !speechStarted && now - started >= 8000;
        const silence = speechStarted && now - lastSpeech >= 1200;
        const tooLong = speechStarted && now - speechStarted >= 30_000;

        if (noSpeech || silence || tooLong) stop();
      }, 50);
    });
  } finally {
    window.clearInterval(timer);

    if (abortRecording) {
      signal.removeEventListener("abort", abortRecording);
    }

    if (recorder?.state === "recording") recorder.stop();

    stream?.getTracks().forEach((track) => track.stop());
    await context.close().catch(() => {});
  }
}