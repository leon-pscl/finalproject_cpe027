import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { Download, Pause, Play } from 'lucide-react';
import { validateAudio } from '../services/mock';
import { formatTimestamp } from '../recording/format';
import { useRecording } from '../recording/useRecording';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { normalizeMath } from '../services/notesMarkdown';
import 'katex/dist/katex.min.css';
import { generateTranscriptionNotes, type TranscriptNote } from '../services/api';
import CodeMirror from '@uiw/react-codemirror';
import { markdown } from '@codemirror/lang-markdown';
import { Decoration, EditorView, ViewPlugin } from '@codemirror/view';
import { RangeSetBuilder } from '@codemirror/state';
import { notesToMarkdown, parseReferences, frontmatterValue, removeFrontmatterTag } from '../services/notesMarkdown';

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
function LoadingBar({ label, progress }: { label: string; progress?: number }) {
  const { progress: globalProgress } = useRecording();
  const value = Math.max(0, Math.min(100, progress ?? globalProgress));
  return (
    <div className="w-full max-w-[20rem] text-center">
      <p className="mb-1 font-mono text-sm uppercase tracking-widest">{label}</p>
      <div className="rounded-lg border border-dashed border-ink p-2">
        <div
          role="progressbar"
          aria-label={label}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(value)}
          className="h-5 border border-ink bg-paper"
        >
          <div className="h-full bg-ink" style={{ width: `${value}%` }} />
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

const footnoteClass = 'cm-note-footnote';

function createFootnoteExtension(
  references: Map<number, { number: number; segmentId: string; text: string; start: number }>,
  onJump: (reference: { number: number; segmentId: string; text: string; start: number }) => void,
) {
  const buildDecorations = (view: EditorView): any => {
    const builder = new RangeSetBuilder<Decoration>();
    for (const range of view.visibleRanges) {
      const text = view.state.doc.sliceString(range.from, range.to);
      const pattern = /\\[(\\d+)\\]/g;
      let match: RegExpExecArray | null;
      while ((match = pattern.exec(text)) !== null) {
        const number = Number(match[1]);
        const reference = references.get(number);
        if (!reference) continue;
        const from = range.from + match.index;
        const to = from + match[0].length;
        builder.add(
          from,
          to,
          Decoration.mark({
            class: footnoteClass,
            attributes: {
              title: reference.text,
              'data-note-ref': String(number),
            },
          }),
        );
      }
    }
    return builder.finish();
  };

  return ViewPlugin.fromClass(
    class {
      decorations: any;
      constructor(view: EditorView) {
        this.decorations = buildDecorations(view);
      }
      update(update: any) {
        if (update.docChanged || update.viewportChanged) {
          this.decorations = buildDecorations(update.view);
        }
      }
    },
    {
      decorations: (instance: any) => instance.decorations,
      eventHandlers: {
        click(event: MouseEvent, view: EditorView) {
          const pos = view.posAtCoords({ x: event.clientX, y: event.clientY }, false);
          if (pos === null) return false;
          const line = view.state.doc.lineAt(pos);
          const offset = pos - line.from;
          const pattern = /\\[(\\d+)\\]/g;
          let match: RegExpExecArray | null;
          while ((match = pattern.exec(line.text)) !== null) {
            if (offset >= match.index && offset <= match.index + match[0].length) {
              const reference = references.get(Number(match[1]));
              if (reference) {
                onJump(reference);
                return true;
              }
            }
          }
          return false;
        },
      },
    },
  );
}

function TranscriptionReady() {
  const { fileName, transcript, jobId, setNotesReady, setTab, seek, seekProcessed, dspUrl } = useRecording();
  const [noteMarkdown, setNoteMarkdown] = useState('');
  const [generatedMarkdown, setGeneratedMarkdown] = useState('');
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false);
  const [notesProgress, setNotesProgress] = useState(0);
  const [noteError, setNoteError] = useState<string | null>(null);
  const [noteEdited, setNoteEdited] = useState(false);
  const [propertiesOpen, setPropertiesOpen] = useState(true);
  const [noteViewMode, setNoteViewMode] = useState<'document' | 'source'>('document');
  const requestedNotesRef = useRef(false);
  const autosaveKey = jobId ? `lectureflow.notes.${jobId}` : null;

  useEffect(() => {
    if (!autosaveKey) return;
    const saved = window.localStorage.getItem(autosaveKey);
    if (saved) {
      setNoteMarkdown(saved);
      setNoteEdited(true);
    }
  }, [autosaveKey]);

  useEffect(() => {
    if (!autosaveKey || !noteMarkdown) return;
    const timer = window.setTimeout(() => {
      window.localStorage.setItem(autosaveKey, noteMarkdown);
    }, 500);
    return () => window.clearTimeout(timer);
  }, [noteMarkdown, autosaveKey]);

  const generateNotes = useCallback(() => {
    if (!jobId || isGeneratingNotes) return;
    if (noteEdited && noteMarkdown.trim() && noteMarkdown !== generatedMarkdown) {
      if (!window.confirm('Replace the generated notes? Your unsaved edits will be lost.')) return;
    }
    setIsGeneratingNotes(true);
    setNotesProgress(0);
    setNoteError(null);
    const timer = window.setInterval(() => {
      setNotesProgress((previous) => Math.min(90, previous + 6));
    }, 200);
    generateTranscriptionNotes(jobId)
      .then((nextNotes) => {
        const markdown = notesToMarkdown(nextNotes, fileName ?? 'lecture', transcript);
        setNoteMarkdown(markdown);
        setGeneratedMarkdown(markdown);
        setNoteEdited(false);
        setNotesReady(true);
      })
      .catch((error: unknown) => {
        setNoteError(error instanceof Error ? error.message : 'Failed to generate notes.');
        setNotesReady(false);
      })
      .finally(() => {
        window.clearInterval(timer);
        setNotesProgress(100);
        setIsGeneratingNotes(false);
      });
  }, [jobId, isGeneratingNotes, noteEdited, noteMarkdown, generatedMarkdown, fileName, transcript, setNotesReady]);

  useEffect(() => {
    if (!jobId || noteMarkdown || isGeneratingNotes || requestedNotesRef.current) return;
    requestedNotesRef.current = true;
    generateNotes();
  }, [jobId, noteMarkdown, isGeneratingNotes, generateNotes]);

  const references = parseReferences(noteMarkdown, transcript);
  const referenceByNumber = useMemo(() => new Map(references.map((reference) => [reference.number, reference])), [references]);
  const jumpToReference = useCallback(
    (reference: { number: number; segmentId: string; text: string; start: number }) => {
      setNotesReady(true);
      setTab('transcriptions');
      if (dspUrl) seekProcessed(reference.start);
      else seek(reference.start);
    },
    [dspUrl, seek, seekProcessed, setNotesReady, setTab],
  );
  const footnoteExtension = useMemo(
    () => createFootnoteExtension(referenceByNumber, jumpToReference),
    [referenceByNumber, jumpToReference],
  );
  const noteTags = frontmatterValue(noteMarkdown, 'tags')
    .replace(/^\\[|\\]$/g, '')
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean);

  const downloadNotes = useCallback(() => {
    const blob = new Blob([noteMarkdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${(fileName ?? 'notes').replace(/[^a-z0-9._-]/gi, '-') || 'notes'}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }, [noteMarkdown, fileName]);

  if (transcript.length === 0) {
    return (
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center">
        <h1 className="text-3xl font-medium">Transcription Ready</h1>
        {isGeneratingNotes ? (
          <div className="mt-6 w-full max-w-[20rem]">
            <LoadingBar label="Generating notes..." progress={notesProgress} />
          </div>
        ) : null}
        <div className="mt-6"><BigWave /></div>
        <p className="mt-2 break-all text-center font-mono text-sm uppercase tracking-wide">{fileName}</p>
        <p className="mt-4 text-center text-neutral-500">No transcription segments were detected.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col items-center">
      <h1 className="text-3xl font-medium">{noteMarkdown ? 'Notes Generated from Transcript' : 'Transcription Ready'}</h1>
      {isGeneratingNotes ? (
        <div className="mt-6 w-full max-w-[20rem]">
          <LoadingBar label="Generating notes..." progress={notesProgress} />
        </div>
      ) : null}
      {!noteMarkdown ? <div className="mt-6"><BigWave /></div> : null}
      <p className="mt-2 break-all text-center font-mono text-sm uppercase tracking-wide">{fileName}</p>

{jobId ? (
        <section className="mt-8 w-full space-y-6 text-left">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-mono text-sm uppercase tracking-widest">Generated Notes</h2>
            <button
              type="button"
              onClick={generateNotes}
              disabled={isGeneratingNotes}
              className="rounded border border-ink bg-ink px-3 py-1 font-mono text-xs text-paper hover:bg-neutral-800 disabled:opacity-50"
            >
              {isGeneratingNotes ? 'Generating...' : 'Generate notes'}
            </button>
          </div>
          {noteError ? <p className="text-sm text-red-700">{noteError}</p> : null}
          {noteMarkdown ? (
            <div className="space-y-4">
              <details open={propertiesOpen} className="rounded border border-neutral-300 bg-paper p-3">
                <summary className="cursor-pointer font-mono text-xs uppercase tracking-wide text-neutral-500">Properties</summary>
                <div className="mt-3 grid gap-2 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs uppercase text-neutral-500">created</span>
                    <span className="font-mono text-xs">{frontmatterValue(noteMarkdown, 'created') || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs uppercase text-neutral-500">updated</span>
                    <span className="font-mono text-xs">{frontmatterValue(noteMarkdown, 'updated') || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs uppercase text-neutral-500">tags</span>
                    <div className="flex flex-wrap justify-end gap-1">
                      {noteTags.map((tag) => (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => {
                            const next = removeFrontmatterTag(noteMarkdown, tag);
                            setNoteMarkdown(next);
                            setNoteEdited(true);
                          }}
                          className="inline-flex items-center gap-1 rounded-full border border-neutral-300 bg-paper px-2 py-0.5 font-mono text-xs text-neutral-600 hover:bg-neutral-200"
                        >
                          {tag} <span aria-hidden="true">x</span>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs uppercase text-neutral-500">type</span>
                    <span className="font-mono text-xs">{frontmatterValue(noteMarkdown, 'type') || '-'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs uppercase text-neutral-500">status</span>
                    <span className="font-mono text-xs">{frontmatterValue(noteMarkdown, 'status') || '-'}</span>
                  </div>
                </div>
              </details>

              <div className="rounded border border-neutral-300 bg-paper">
                <div className="flex items-center gap-1 border-b border-neutral-300 p-1">
                  <span className="px-2 py-1 font-mono text-xs text-neutral-500">Note Editor</span>
                  <div className="ml-auto flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setNoteViewMode('document')}
                      className={`rounded px-2 py-1 font-mono text-xs hover:bg-neutral-200 ${noteViewMode === 'document' ? 'bg-neutral-200' : ''}`}
                    >
                      Document
                    </button>
                    <button
                      type="button"
                      onClick={() => setNoteViewMode('source')}
                      className={`rounded px-2 py-1 font-mono text-xs hover:bg-neutral-200 ${noteViewMode === 'source' ? 'bg-neutral-200' : ''}`}
                    >
                      Source
                    </button>
                    <button
                    type="button"
                    onClick={downloadNotes}
                    disabled={!noteMarkdown}
                    className="ml-auto inline-flex items-center rounded bg-ink px-2 py-1 font-mono text-xs text-paper hover:bg-neutral-800 disabled:opacity-50"
                    aria-label="Download markdown"
                    title="Download markdown"
                  >
                    <Download size={14} aria-hidden="true" />
                  </button>
                  </div>
                </div>
                <style>{'.cm-note-footnote { font-size: 0.75em; vertical-align: super; text-decoration: underline; text-decoration-style: dotted; cursor: pointer; color: inherit; }'}</style>
                {noteViewMode === 'document' ? (
                  <div className="max-h-[80vh] overflow-y-auto p-4 font-mono text-sm leading-6">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeKatex]}
                      components={{
                        h1: ({ children }) => <h1 className="text-3xl font-medium">{children}</h1>,
                        h2: ({ children }) => <h2 className="mb-2 mt-4 font-mono text-sm uppercase tracking-widest">{children}</h2>,
                        h3: ({ children }) => <h3 className="mb-1 mt-3 font-mono text-xs uppercase tracking-wide">{children}</h3>,
                        p: ({ children }) => <p className="mb-2 leading-6">{children}</p>,
                        ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 pl-5">{children}</ul>,
                        ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 pl-5">{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        hr: () => <hr className="my-4 border-neutral-300" />,
                        code: ({ children }) => <code className="rounded bg-neutral-100 px-1 py-0.5 font-mono text-xs">{children}</code>,
                      }}
                    >
                      {normalizeMath(noteMarkdown)}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <CodeMirror
                    value={noteMarkdown}
                    height="640px"
                    extensions={[markdown(), EditorView.lineWrapping, footnoteExtension]}
                    onChange={(value) => {
                      setNoteMarkdown(value);
                      setNoteEdited(true);
                    }}
                    basicSetup={{
                      lineNumbers: false,
                      foldGutter: false,
                      dropCursor: false,
                      allowMultipleSelections: false,
                      indentOnInput: true,
                      bracketMatching: true,
                      closeBrackets: true,
                      autocompletion: false,
                      rectangularSelection: false,
                      crosshairCursor: false,
                      highlightActiveLine: true,
                      highlightActiveLineGutter: false,
                      highlightSelectionMatches: false,
                      searchKeymap: false,
                    }}
                    className="font-mono text-sm max-h-[80vh]"
                  />
                )}
              </div>

              {references.length ? (
                  <section className="space-y-2">
                    <h3 className="font-mono text-xs uppercase tracking-wide text-neutral-500">Sources</h3>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const first = references[0];
                          setNotesReady(true);
                          setTab('transcriptions');
                          if (dspUrl) seekProcessed(first.start);
                          else seek(first.start);
                        }}
                        className="rounded-full border border-neutral-300 bg-paper px-3 py-1 font-mono text-xs text-neutral-700 hover:bg-neutral-200"
                        title={references.map((reference) => reference.text).join(' ')}
                      >
                        Recording transcript ({references.length} cited)
                      </button>
                    </div>
                  </section>
                ) : null}
            </div>
          ) : (
            <p className="text-sm text-neutral-500">No notes generated yet.</p>
          )}
        </section>
      ) : null}
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
  const { stage, progress, fileError: uploadError, start } = useRecording();
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
      {stage === 'dsp' ? <LoadingBar label="Cleaning audio via DSP..." progress={Math.min(100, progress * 10)} /> : null}

      {stage === 'transcribing' ? (
        <LoadingBar label="Transcribing..." progress={Math.min(100, Math.max(0, (progress - 10) / 90 * 100))} />
      ) : null}
      {stage === 'generatingNotes' ? <LoadingBar label="Generating notes..." /> : null}
    </div>
  );
}