import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { Clock } from 'lucide-react';
import { formatTimestamp } from '../services/mock';
import { useRecording } from '../recording/useRecording';

/* ---------- Frame 1: Input Recording ---------- */
function DropZone() {
  const { start, fileError } = useRecording();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) start(file);
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
            dragging ? 'bg-accent' : 'bg-paper'
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
            if (file) start(file);
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

/* ---------- Frames 2 & 3: Loading | Transcribe / Generate Notes ---------- */
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

/* ---------- Frames 4 & 5: Transcription Ready ---------- */
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

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col items-center">
      <h1 className="text-3xl font-medium">Transcription Ready</h1>
      <div className="mt-6">
        <BigWave />
      </div>
      <p className="mt-2 break-all text-center font-mono text-sm uppercase tracking-wide">{fileName}</p>

      {/* One grid for every row => time, waveform and text line up in fixed columns. */}
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
                  active ? 'bg-accent' : ''
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

export default function NewRecordingPage() {
  const { stage } = useRecording();

  if (stage === 'ready') {
    return (
      <div className="pt-4">
        <TranscriptionReady />
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      {stage === 'idle' ? <DropZone /> : null}
      {stage === 'transcribing' ? <LoadingBar label="Transcribing..." /> : null}
      {stage === 'generatingNotes' ? <LoadingBar label="Generating notes..." /> : null}
    </div>
  );
}
