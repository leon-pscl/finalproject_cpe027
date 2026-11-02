import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { Clock, Pause, Play } from 'lucide-react';
import { validateAudio } from '../services/mock';
import { formatTimestamp } from '../recording/format';
import { useRecording } from '../recording/useRecording';

/* ---------- Frame 1: Input Recording ---------- */
function DropZone({ onFile, fileError }: { onFile: (file: File) => void; fileError: string | null }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) onFile(file);
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      inputRef.current?.click();
    }
  };

  return (
    <div className="w-full max-w-[26rem]">
      <div className="rounded-lg border border-dashed border-ink p-3">
        <div
          role="button"
          tabIndex={0}
          aria-label="Drag a recording here, or press Enter to choose a file"
          onClick={() => inputRef.current?.click()}
          onKeyDown={onKeyDown}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex h-56 cursor-pointer items-center justify-center border border-ink text-sm text-neutral-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
            dragging ? 'bg-slate-200' : 'bg-paper'
          }`}
        >
          drag recording here
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".wav,.mp3,.m4a,audio/*"
          aria-label="Recording file"
          className="sr-only"
          tabIndex={-1}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = '';
          }}
        />
      </div>
      <p className="mt-2 text-center text-xs text-neutral-500">WAV, MP3 or M4A</p>
      {fileError ? (
        <p role="alert" className="mt-2 text-center text-sm text-red-700">
          {fileError}
        </p>
      ) : null}
    </div>
  );
}

/* ---------- Frame 2/3: Loading ---------- */
function LoadingBar({ label }: { label: string }) {
  const { progress } = useRecording();
  return (
    <div className="w-full max-w-[20rem] text-center">
      <p className="mb-1 font-mono text-sm uppercase tracking-widest">{label}</p>
      <div className="rounded-lg border border-dashed border-ink p-2">
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
          className="h-5 border border-ink bg-paper"
        >
          <div className="h-full bg-ink" style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  );
}

/* ---------- Frame 4/5: Ready ---------- */
function BigWave() {
  return (
    <svg viewBox="0 0 260 130" aria-hidden="true" className="h-32 w-64">
      <path
        d="M4 62 C 20 62, 24 20, 40 20 H 62 C 74 20, 74 108, 86 108 H 100 C 112 108, 112 8, 124 8 H 146 C 158 8, 158 92, 170 92 H 186 C 200 92, 204 52, 214 48 H 256"
        fill="none"
        stroke="#000"
        strokeWidth="1.6"
        transform="translate(0 4)"
      />
    </svg>
  );
}

/** Deterministic mini waveform so a row always draws the same bars. */
function MiniWave({ seed }: { seed: number }) {
  const bars = Array.from({ length: 26 }, (_, i) => {
    const v = Math.abs(Math.sin((i + 1) * (seed + 3) * 0.9)) * 0.75 + 0.2;
    return Math.round(v * 20);
  });
  return (
    <svg viewBox="0 0 104 24" aria-hidden="true" className="h-6 w-[6.5rem]">
      {bars.map((height, i) => (
        <rect key={i} x={i * 4} y={12 - height / 2} width="1.6" height={height} fill="#000" />
      ))}
    </svg>
  );
}

function TranscriptionReady() {
  const { fileName, transcript, player, seek } = useRecording();

  if (transcript.length === 0) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col items-center">
        <h1 className="text-3xl font-medium">Transcription Ready</h1>
        <div className="mt-6"><BigWave /></div>
        <p className="mt-2 break-all text-center font-mono text-sm uppercase tracking-wide">{fileName}</p>
        <p className="mt-4 text-center text-neutral-500">No transcription segments were detected.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center">
      <h1 className="text-3xl font-medium">Transcription Ready</h1>
      <div className="mt-6"><BigWave /></div>
      <p className="mt-2 break-all text-center font-mono text-sm uppercase tracking-wide">{fileName}</p>

      <ul className="mt-10 grid w-full grid-cols-[4rem_6.5rem_minmax(0,1fr)] gap-x-4 gap-y-2">
        {transcript.map((segment, index) => {
          const next = transcript[index + 1];
          const active = player.currentTime >= segment.start && (!next || player.currentTime < next.start);
          return (
            <li key={segment.id} className="col-span-3 grid grid-cols-subgrid">
              <button
                type="button"
                onClick={() => seek(segment.start)}
                aria-label={`Jump to ${formatTimestamp(segment.start)}`}
                aria-current={active ? 'true' : undefined}
                className={`col-span-3 grid grid-cols-subgrid items-center py-2 text-left hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink ${
                  active ? 'bg-slate-200' : ''
                }`}
              >
                <span className="flex flex-col items-center font-mono text-sm">
                  <Clock size={18} aria-hidden="true" />
                  {formatTimestamp(segment.start)}
                </span>
                <MiniWave seed={index} />
                <span className="text-sm">
                  <span className="text-neutral-500">Text: </span>
                  {segment.text}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function RecordingPreview({ src }: { src: string; }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrent(audio.currentTime);
    const onMeta = () => setDuration(Number.isFinite(audio.duration) ? audio.duration : 0);
    const onEnded = () => setPlaying(false);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('loadedmetadata', onMeta);
    audio.addEventListener('ended', onEnded);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('loadedmetadata', onMeta);
      audio.removeEventListener('ended', onEnded);
    };
  }, [src]);

  return (
    <div className="mt-3 rounded-lg border border-dashed border-ink bg-paper p-2 font-mono">
      <audio ref={audioRef} src={src} preload="metadata" className="sr-only" />
      <div className="flex items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => {
            if (!audioRef.current) return;
            if (playing) audioRef.current.pause();
            else void audioRef.current.play();
            setPlaying(!playing);
          }}
          className="inline-flex h-9 items-center justify-center gap-2 rounded border border-ink bg-ink px-3 text-xs font-medium text-paper hover:bg-neutral-800"
        >
          {playing ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
          {playing ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={duration || 0}
          step={0.1}
          value={current}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (audioRef.current) audioRef.current.currentTime = next;
            setCurrent(next);
          }}
          aria-label="Selected recording position"
          className="h-1 flex-1 accent-ink"
        />
        <span className="text-xs text-neutral-500">
          {formatTimestamp(current)} / {formatTimestamp(duration)}
        </span>
      </div>
    </div>
  );
}

export default function NewRecordingPage() {
  const { stage, fileError: uploadError, start } = useRecording();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileError, setSelectedFileError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedFile]);

  if (stage === 'ready') {
    return (
      <div className="pt-4">
        <TranscriptionReady />
      </div>
    );
  }

  if (selectedFile && previewUrl) {
    const error = selectedFileError || uploadError;
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
        <div className="w-full max-w-[26rem] text-center">
          <p className="font-mono text-sm uppercase tracking-widest">Review recording</p>
          <RecordingPreview src={previewUrl} />
          <p className="mt-2 break-all font-mono text-xs uppercase tracking-wide text-neutral-500">{selectedFile.name}</p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => {
                setSelectedFile(null);
                setSelectedFileError(null);
                start(selectedFile).catch((error: unknown) => {
                  setSelectedFileError(error instanceof Error ? error.message : 'Upload failed.');
                });
              }}
              className="inline-flex min-h-[44px] items-center justify-center rounded border border-ink bg-ink px-4 py-2.5 font-mono text-sm font-medium text-paper hover:bg-neutral-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
            >
              Start processing
            </button>
            <button
              type="button"
              onClick={() => {
                setSelectedFile(null);
                setSelectedFileError(null);
              }}
              className="inline-flex min-h-[44px] items-center justify-center rounded border border-ink bg-paper px-4 py-2.5 font-mono text-sm font-medium text-ink hover:bg-neutral-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink"
            >
              Delete
            </button>
          </div>
          {error ? (
            <p role="alert" className="mt-2 text-sm text-red-700">
              {error}
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      {stage === 'idle' ? (
        <DropZone
          fileError={selectedFileError || uploadError}
          onFile={(file) => {
            const validation = validateAudio(file);
            if (!validation.isValid) {
              setSelectedFileError(validation.message ?? 'Unsupported file.');
              setSelectedFile(null);
              return;
            }
            setSelectedFileError(null);
            setSelectedFile(file);
          }}
        />
      ) : null}
      {stage === 'dsp' ? <LoadingBar label="Cleaning audio via DSP..." /> : null}

      {stage === 'transcribing' ? <LoadingBar label="Transcribing..." /> : null}
      {stage === 'generatingNotes' ? <LoadingBar label="Generating notes..." /> : null}
    </div>
  );
}