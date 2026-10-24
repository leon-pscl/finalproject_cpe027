import { useEffect, useMemo, useState, type Dispatch, type FormEvent, type ReactNode, type SetStateAction } from 'react';
import {
  AlertCircle,
  AudioLines,
  Check,
  ChevronDown,
  Copy,
  FileText,
  FolderOpen,
  Gauge,
  ListFilter,
  NotebookPen,
  Pencil,
  Play,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import {
  Navigate,
  Route,
  Routes,
  useNavigate,
  useParams,
} from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { ProtectedRoute } from './auth/ProtectedRoute';
import AppShell from './layouts/AppShell';
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import NewRecordingPage from './pages/NewRecordingPage';
import RecordingsPage from './pages/RecordingsPage';
import SearchPage from './pages/SearchPage';
import {
  buildLectureProject,
  createBlobFromText,
  exportNotesAsMarkdown,
  exportProjectJson,
  exportTranscriptAsText,
  formatTimestamp,
  getDspSettings,
  inspectAudio,
  validateAudio,
  type DspPreset,
  type DspSettings,
  type LectureProject,
  type WorkflowState,
} from './services/mock';

type StatusTone = 'completed' | 'processing' | 'failed';

type ViewTab = 'transcript' | 'notes' | 'details';

type FormState = {
  file: File | null;
  title: string;
  subject: string;
  instructor: string;
  language: string;
  preset: DspPreset;
  dspSettings: DspSettings;
};

type ValidationErrors = Partial<Record<'file' | 'title', string>>;

const stageOrder: WorkflowState[] = [
  'validating',
  'processingDSP',
  'transcribing',
  'indexing',
  'generatingNotes',
  'completed',
];

const emptyForm: FormState = {
  file: null,
  title: '',
  subject: '',
  instructor: '',
  language: 'English',
  preset: 'automatic',
  dspSettings: getDspSettings('automatic'),
};

function App() {
  const [lectures, setLectures] = useState<LectureProject[]>([]);

  const updateLecture = (lectureId: string, updater: (lecture: LectureProject) => LectureProject) => {
    setLectures((current) => current.map((project) => (project.id === lectureId ? updater(project) : project)));
  };

  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/recordings" element={<RecordingsPage />} />
            <Route path="/new-transcription" element={<NewRecordingPage />} />
            <Route path="/new-transcription/advanced" element={<NewTranscriptionPage updateLectures={setLectures} />} />
            <Route path="/processing/:id" element={<ProcessingPage lectures={lectures} updateLecture={updateLecture} />} />
            <Route path="/results/:id" element={<ResultsPage lectures={lectures} updateLecture={updateLecture} />} />
            <Route path="/recent-lectures" element={<RecentLecturesPage lectures={lectures} setLectures={setLectures} />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

function NewTranscriptionPage({ updateLectures }: { updateLectures: Dispatch<SetStateAction<LectureProject[]>> }) {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [errors, setErrors] = useState<ValidationErrors>({});
  const [isDragging, setIsDragging] = useState(false);

  const fileInfo = useMemo(() => inspectAudio(form.file), [form.file]);

  const handlePresetChange = (preset: DspPreset) => {
    setForm((current) => ({
      ...current,
      preset,
      dspSettings: getDspSettings(preset),
    }));
  };

  const handleFileSelection = (nextFile: File | null) => {
    const validation = validateAudio(nextFile);
    if (nextFile && !validation.isValid) {
      setErrors((current) => ({ ...current, file: validation.message }));
      return;
    }

    setErrors((current) => ({ ...current, file: undefined }));
    setForm((current) => ({ ...current, file: nextFile }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextErrors: ValidationErrors = {};

    if (!form.file) {
      nextErrors.file = 'Please choose an audio file.';
    } else if (!validateAudio(form.file).isValid) {
      nextErrors.file = validateAudio(form.file).message;
    }

    if (!form.title.trim()) {
      nextErrors.title = 'Lecture title is required.';
    }

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    const createdProject = buildLectureProject({
      title: form.title.trim(),
      subject: form.subject.trim() || 'General lecture',
      instructor: form.instructor.trim() || 'Unspecified',
      language: form.language,
      file: form.file as File,
      dspPreset: form.preset,
      dspSettings: form.dspSettings,
    });

    const project: LectureProject = {
      ...createdProject,
      id: `lecture-${Date.now()}`,
      status: 'Processing',
      workflowState: 'fileSelected',
      createdAt: new Date().toISOString(),
      processingDetails: {
        ...createdProject.processingDetails,
        processingStatus: 'Queued',
      },
    };

    updateLectures((current) => [project, ...current]);
    navigate(`/processing/${project.id}`);
  };

  const isSubmitDisabled = !form.file || !form.title.trim() || !validateAudio(form.file).isValid;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">New transcription</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-50">Process a lecture</h1>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div
            className={`rounded-2xl border-2 border-dashed p-5 transition ${
              isDragging
                ? 'border-teal-500 bg-teal-50 dark:bg-teal-950/20'
                : 'border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60'
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              const droppedFile = event.dataTransfer.files?.[0] ?? null;
              handleFileSelection(droppedFile);
            }}
          >
            <div className="flex flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300">
                <Upload size={22} />
              </div>
              <div>
                <p className="text-base font-medium text-slate-900 dark:text-slate-100">Drag and drop your lecture audio</p>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Accepted formats: WAV, MP3, M4A</p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-3">
                <label className="inline-flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 focus-within:outline-none focus-within:ring-2 focus-within:ring-teal-500 dark:bg-slate-700 dark:hover:bg-slate-600">
                  <FolderOpen size={16} />
                  Browse files
                  <input
                    type="file"
                    accept=".wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4"
                    className="sr-only"
                    onChange={(event) => handleFileSelection(event.target.files?.[0] ?? null)}
                    aria-label="Choose lecture audio file"
                  />
                </label>
                {form.file ? (
                  <button
                    type="button"
                    onClick={() => setForm((current) => ({ ...current, file: null }))}
                    className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Remove file
                  </button>
                ) : null}
              </div>
            </div>
          </div>

          {errors.file ? (
            <p className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400" role="alert">
              <AlertCircle size={15} />
              {errors.file}
            </p>
          ) : null}

          {fileInfo ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="grid gap-3 text-sm text-slate-700 dark:text-slate-200 sm:grid-cols-2">
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">File name</div>
                  <div className="mt-1 font-medium">{fileInfo.name}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">File type</div>
                  <div className="mt-1 font-medium">{fileInfo.type}</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Size</div>
                  <div className="mt-1 font-medium">{(fileInfo.size / 1024 / 1024).toFixed(2)} MB</div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Estimated duration</div>
                  <div className="mt-1 font-medium">{fileInfo.estimatedDuration}s</div>
                </div>
              </div>
            </div>
          ) : null}

          <div className="grid gap-5 md:grid-cols-2">
            <Field label="Lecture title" htmlFor="title">
              <input
                id="title"
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                placeholder="Week 5: Sampling and reconstruction"
                aria-invalid={Boolean(errors.title)}
              />
              {errors.title ? <ErrorText message={errors.title} /> : null}
            </Field>
            <Field label="Subject or course" htmlFor="subject">
              <input
                id="subject"
                value={form.subject}
                onChange={(event) => setForm((current) => ({ ...current, subject: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                placeholder="Digital Signal Processing"
              />
            </Field>
            <Field label="Instructor" htmlFor="instructor">
              <input
                id="instructor"
                value={form.instructor}
                onChange={(event) => setForm((current) => ({ ...current, instructor: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                placeholder="Dr. Lewis"
              />
            </Field>
            <Field label="Language" htmlFor="language">
              <select
                id="language"
                value={form.language}
                onChange={(event) => setForm((current) => ({ ...current, language: event.target.value }))}
                className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              >
                <option>English</option>
                <option>Spanish</option>
                <option>French</option>
                <option>German</option>
              </select>
            </Field>
          </div>
        </div>

        <aside className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Audio enhancement settings</h2>
            <button type="button" className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-300" aria-label="Toggle audio enhancement section">
              <ChevronDown size={16} />
              Expand
            </button>
          </div>

          <div className="space-y-4">
            <div>
              <label htmlFor="preset" className="text-sm font-medium text-slate-700 dark:text-slate-200">Processing preset</label>
              <select
                id="preset"
                value={form.preset}
                onChange={(event) => handlePresetChange(event.target.value as DspPreset)}
                className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
              >
                <option value="automatic">Automatic</option>
                <option value="quiet-room">Quiet room</option>
                <option value="noisy-classroom">Noisy classroom</option>
                <option value="custom">Custom</option>
              </select>
            </div>

            <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/60">
              {Object.entries(form.dspSettings).map(([key, value]) => (
                <ToggleSetting
                  key={key}
                  label={
                    key === 'noiseReduction'
                      ? 'Noise reduction'
                      : key === 'highPassFilter'
                        ? 'High-pass filtering'
                        : key === 'loudnessNormalization'
                          ? 'Loudness normalization'
                          : key === 'voiceActivityDetection'
                            ? 'Voice activity detection'
                            : key === 'silenceRemoval'
                              ? 'Silence removal'
                              : 'Audio segmentation'
                  }
                  checked={Boolean(value)}
                  onChange={() =>
                    setForm((current) => ({
                      ...current,
                      preset: 'custom',
                      dspSettings: {
                        ...current.dspSettings,
                        [key]: !value,
                      },
                    }))
                  }
                />
              ))}
            </div>

            <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
              These processing options are demonstration controls for the prototype and are not active model settings yet.
            </div>

            <button
              type="submit"
              disabled={isSubmitDisabled}
              className="inline-flex min-h-[48px] w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-teal-500 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 dark:disabled:bg-slate-700 dark:disabled:text-slate-400"
            >
              <Sparkles size={16} />
              Start processing
            </button>
          </div>
        </aside>
      </form>
    </div>
  );
}

function ToggleSetting({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
      <span>{label}</span>
      <button
        type="button"
        onClick={onChange}
        aria-label={label}
        className={`relative inline-flex h-7 w-12 items-center rounded-full transition ${checked ? 'bg-teal-600' : 'bg-slate-300 dark:bg-slate-600'}`}
      >
        <span className={`inline-block h-5 w-5 rounded-full bg-white transition ${checked ? 'translate-x-6' : 'translate-x-1'}`} />
      </button>
    </label>
  );
}

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700 dark:text-slate-200">
      {label}
      {children}
    </label>
  );
}

function ErrorText({ message }: { message: string }) {
  return (
    <p className="mt-2 flex items-center gap-2 text-sm text-red-600 dark:text-red-400" role="alert">
      <AlertCircle size={15} />
      {message}
    </p>
  );
}

function ProcessingPage({
  lectures,
  updateLecture,
}: {
  lectures: LectureProject[];
  updateLecture: (lectureId: string, updater: (lecture: LectureProject) => LectureProject) => void;
}) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [shouldFail, setShouldFail] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  const lecture = lectures.find((project) => project.id === id);

  useEffect(() => {
    if (!lecture || lecture.workflowState === 'completed' || lecture.workflowState === 'failed' || lecture.workflowState === 'cancelled') {
      return;
    }

    if (shouldFail) {
      updateLecture(lecture.id, (project) => ({
        ...project,
        status: 'Failed',
        workflowState: 'failed',
        processingDetails: { ...project.processingDetails, processingStatus: 'Failed' },
      }));
      return;
    }

    if (cancelled) {
      updateLecture(lecture.id, (project) => ({
        ...project,
        workflowState: 'cancelled',
        status: 'Processing',
        processingDetails: { ...project.processingDetails, processingStatus: 'Cancelled' },
      }));
      return;
    }

    if (currentStageIndex >= stageOrder.length - 1) {
      const finalizedProject: LectureProject = {
        ...lecture,
        status: 'Completed',
        workflowState: 'completed',
        processingDetails: {
          ...lecture.processingDetails,
          processingStatus: 'Completed',
        },
      };

      updateLecture(lecture.id, () => finalizedProject);
      const timer = window.setTimeout(() => navigate(`/results/${lecture.id}`), 700);
      return () => window.clearTimeout(timer);
    }

    const timer = window.setTimeout(() => {
      const nextIndex = Math.min(currentStageIndex + 1, stageOrder.length - 1);
      setCurrentStageIndex(nextIndex);
      updateLecture(lecture.id, (project) => ({
        ...project,
        workflowState: stageOrder[nextIndex],
        status: 'Processing',
        processingDetails: {
          ...project.processingDetails,
          processingStatus: stageOrder[nextIndex],
        },
      }));
    }, 900);

    return () => window.clearTimeout(timer);
  }, [cancelled, currentStageIndex, lecture, navigate, shouldFail, updateLecture]);

  if (!lecture) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">Project not found.</div>;
  }

  const currentStage = stageOrder[currentStageIndex] ?? 'completed';
  const progress = Math.min(100, ((currentStageIndex + 1) / stageOrder.length) * 100);

  const activeStageLabel =
    currentStage === 'validating'
      ? 'Validating audio'
      : currentStage === 'processingDSP'
        ? 'Standardizing audio format'
        : currentStage === 'transcribing'
          ? 'Applying DSP enhancement'
          : currentStage === 'indexing'
            ? 'Detecting speech segments'
            : currentStage === 'generatingNotes'
              ? 'Transcribing speech'
              : 'Generating lecture notes';

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">Processing</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-50">{lecture.title}</h1>
        </div>
        <button
          type="button"
          onClick={() => setCancelled(true)}
          className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-slate-600 dark:text-slate-300">Current stage</p>
            <p className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-50">{activeStageLabel}</p>
          </div>
          <div className="rounded-full bg-slate-100 px-3 py-1 text-sm font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">
            {Math.round(progress)}%
          </div>
        </div>

        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div className="h-full rounded-full bg-teal-600 transition-all duration-500" style={{ width: `${progress}%` }} />
        </div>

        <ol className="mt-6 space-y-3" aria-live="polite">
          {stageOrder.map((stage, index) => {
            const isCurrent = index === currentStageIndex;
            const isCompleted = index < currentStageIndex;
            const isFailed = lecture.workflowState === 'failed';

            return (
              <li key={stage} className="flex items-center gap-3">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${
                    isFailed
                      ? 'bg-red-600 text-white'
                      : isCompleted
                        ? 'bg-teal-600 text-white'
                        : isCurrent
                          ? 'bg-slate-900 text-white dark:bg-slate-200 dark:text-slate-900'
                          : 'bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                  }`}
                >
                  {isFailed ? (
                    <X className="h-3.5 w-3.5" />
                  ) : isCompleted ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span className={`text-sm ${isCurrent ? 'font-medium text-slate-900 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'}`}>
                  {stage === 'validating'
                    ? 'Validating audio'
                    : stage === 'processingDSP'
                      ? 'Standardizing audio format'
                      : stage === 'transcribing'
                        ? 'Applying DSP enhancement'
                        : stage === 'indexing'
                          ? 'Detecting speech segments'
                          : stage === 'generatingNotes'
                            ? 'Transcribing speech'
                            : 'Generating lecture notes'}
                </span>
              </li>
            );
          })}
        </ol>

        {lecture.workflowState === 'failed' ? (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/20 dark:text-red-200">
            <div className="mb-2 flex items-center gap-2 font-semibold">
              <AlertCircle size={16} />
              Mock processing failed
            </div>
            <p>The simulation intentionally failed to test retry and recovery behavior.</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => {
                  setShouldFail(false);
                  setCurrentStageIndex(0);
                  updateLecture(lecture.id, (project) => ({
                    ...project,
                    status: 'Processing',
                    workflowState: 'validating',
                    processingDetails: { ...project.processingDetails, processingStatus: 'Retrying' },
                  }));
                }}
                className="inline-flex min-h-[44px] items-center justify-center rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={() => navigate('/new-transcription')}
                className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Return to upload
              </button>
            </div>
          </div>
        ) : null}

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => setShouldFail(true)}
            className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-800 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
          >
            <Gauge size={16} />
            Trigger mock failure
          </button>
        </div>
      </section>
    </div>
  );
}

function ResultsPage({ lectures, updateLecture }: { lectures: LectureProject[]; updateLecture: (lectureId: string, updater: (lecture: LectureProject) => LectureProject) => void }) {
  const { id } = useParams();
  const lecture = lectures.find((project) => project.id === id) ?? lectures[0];
  const [activeTab, setActiveTab] = useState<ViewTab>('transcript');
  const [searchTerm, setSearchTerm] = useState('');
  const [showConfidence, setShowConfidence] = useState(true);
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(lecture?.transcript[0]?.id ?? null);

  useEffect(() => {
    if (lecture?.transcript[0]) {
      setSelectedSegmentId(lecture.transcript[0].id);
    }
  }, [lecture]);

  if (!lecture) {
    return <div className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">No lecture results available.</div>;
  }

  const filteredSegments = lecture.transcript.filter((segment) =>
    segment.text.toLowerCase().includes(searchTerm.toLowerCase()) || segment.speaker.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const handleExport = (format: string) => {
    const anchor = document.createElement('a');
    let content = '';
    let fileName = `${lecture.title}.txt`;
    let mime = 'text/plain;charset=utf-8';

    if (format === 'transcript') {
      content = exportTranscriptAsText(lecture);
      fileName = `${lecture.title}-transcript.txt`;
    }
    if (format === 'notes') {
      content = exportNotesAsMarkdown(lecture);
      fileName = `${lecture.title}-notes.md`;
      mime = 'text/markdown;charset=utf-8';
    }
    if (format === 'json') {
      content = exportProjectJson(lecture);
      fileName = `${lecture.title}-project.json`;
      mime = 'application/json;charset=utf-8';
    }

    const blob = createBlobFromText(content, mime);
    const url = URL.createObjectURL(blob);
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectTimestamp = (segmentId: string) => {
    setSelectedSegmentId(segmentId);
    if (activeTab !== 'transcript') {
      setActiveTab('transcript');
    }
    const target = document.getElementById(`segment-${segmentId}`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const handleSourceReference = (references: string[]) => {
    const firstRef = references[0];
    const matched = lecture.transcript.find((segment) => formatTimestamp(segment.start) === firstRef);
    if (matched) {
      handleSelectTimestamp(matched.id);
    }
  };

  return (
    <div className="space-y-6">
      <header className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">Results workspace</p>
            <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-50">{lecture.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-slate-600 dark:text-slate-300">
              <span>{lecture.subject}</span>
              <span>•</span>
              <span>{lecture.instructor || 'Unspecified instructor'}</span>
              <span>•</span>
              <span>{lecture.language}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              <Play size={16} />
              Play audio
            </button>
            <label className="inline-flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2.5 text-sm text-slate-700 dark:border-slate-600 dark:text-slate-200">
              <span>Export</span>
              <select
                defaultValue=""
                onChange={(event) => {
                  const value = event.target.value;
                  if (value) {
                    handleExport(value);
                    event.target.value = '';
                  }
                }}
                className="bg-transparent text-sm outline-none"
                aria-label="Export lecture data"
              >
                <option value="">Choose</option>
                <option value="transcript">Plain-text transcript</option>
                <option value="notes">Markdown notes</option>
                <option value="json">JSON project data</option>
                <option disabled value="pdf">PDF export (Planned)</option>
                <option disabled value="docx">DOCX export (Planned)</option>
              </select>
            </label>
          </div>
        </div>
      </header>

      <div className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="space-y-4">
            <div className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/70">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-700 dark:text-slate-200">
                  <AudioLines size={16} />
                  Audio preview
                </div>
                <button type="button" className="text-xs text-teal-700 dark:text-teal-300">{showConfidence ? 'Visible' : 'Hidden'}</button>
              </div>
              <div className="mt-3 rounded-xl bg-slate-900 p-3 text-slate-100 dark:bg-slate-950">
                <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-wide text-slate-300">
                  <span>{lecture.fileName}</span>
                  <span>{lecture.duration}s</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-700">
                  <div className="h-full w-2/5 rounded-full bg-teal-400" />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h2 className="text-sm font-semibold uppercase tracking-[0.15em] text-slate-500 dark:text-slate-400">Navigation</h2>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${
                  activeTab === 'transcript' ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'
                }`}
                onClick={() => setActiveTab('transcript')}
              >
                <span className="flex items-center gap-2"><FileText size={15} /> Transcript</span>
                <span>{lecture.transcript.length}</span>
              </button>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${
                  activeTab === 'notes' ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'
                }`}
                onClick={() => setActiveTab('notes')}
              >
                <span className="flex items-center gap-2"><NotebookPen size={15} /> Notes</span>
                <span>{lecture.notes.length}</span>
              </button>
              <button
                type="button"
                className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${
                  activeTab === 'details' ? 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100' : 'text-slate-600 dark:text-slate-300'
                }`}
                onClick={() => setActiveTab('details')}
              >
                <span className="flex items-center gap-2"><ListFilter size={15} /> Processing details</span>
                <span>Config</span>
              </button>
            </div>
          </div>
        </aside>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-5">
          {activeTab === 'transcript' ? (
            <div className="space-y-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex-1">
                  <label htmlFor="transcript-search" className="sr-only">Search transcript</label>
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                    <input
                      id="transcript-search"
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                      className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-10 pr-3 text-sm text-slate-900 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-200 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
                      placeholder="Search transcript"
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowConfidence((value) => !value)}
                  className="inline-flex min-h-[44px] items-center justify-center rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  {showConfidence ? 'Hide confidence' : 'Show confidence'}
                </button>
              </div>

              <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
                {filteredSegments.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    No transcript segments match your search.
                  </div>
                ) : (
                  filteredSegments.map((segment) => (
                    <div
                      key={segment.id}
                      id={`segment-${segment.id}`}
                      className={`rounded-2xl border p-4 transition ${selectedSegmentId === segment.id ? 'border-teal-500 bg-teal-50 dark:border-teal-700 dark:bg-teal-950/20' : 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/60'}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <button
                          type="button"
                          onClick={() => handleSelectTimestamp(segment.id)}
                          className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-100"
                        >
                          {formatTimestamp(segment.start)}
                        </button>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">{segment.speaker}</span>
                          {showConfidence && segment.confidence < 0.75 ? (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                              Low confidence
                            </span>
                          ) : null}
                        </div>
                      </div>

                      <p className="mt-3 text-base leading-7 text-slate-700 dark:text-slate-200">
                        <span dangerouslySetInnerHTML={{ __html: highlightMatch(segment.text, searchTerm) }} />
                      </p>

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleSelectTimestamp(segment.id)}
                          className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                          <Play size={15} />
                          Jump to timestamp
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            const updatedTranscript = lecture.transcript.map((item) =>
                              item.id === segment.id ? { ...item, text: item.text } : item,
                            );
                            updateLecture(lecture.id, (project) => ({
                              ...project,
                              transcript: updatedTranscript,
                            }));
                          }}
                          className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                          <Pencil size={15} />
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => navigator.clipboard.writeText(segment.text)}
                          className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                        >
                          <Copy size={15} />
                          Copy
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}

          {activeTab === 'notes' ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Generated notes</h2>
                <button
                  type="button"
                  className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500"
                >
                  <Sparkles size={16} />
                  Regenerate notes
                </button>
              </div>

              <div className="space-y-4">
                {lecture.notes.map((note) => (
                  <article key={note.id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">{note.section}</p>
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{note.title}</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-700 dark:text-slate-200">{note.description}</p>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {note.references.map((ref) => (
                        <button
                          key={ref}
                          type="button"
                          onClick={() => handleSourceReference(note.references)}
                          className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-700 hover:bg-teal-100 dark:border-teal-800 dark:bg-teal-950/30 dark:text-teal-200"
                        >
                          {ref}
                        </button>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {activeTab === 'details' ? (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-50">Processing details</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <DetailCard label="Original file" value={lecture.fileName} />
                <DetailCard label="DSP preset" value={lecture.dspPreset} />
                <DetailCard label="Enabled DSP operations" value={lecture.processingDetails.enabledOperations.join(', ') || 'None'} />
                <DetailCard label="ASR model placeholder" value={lecture.processingDetails.asrModel} />
                <DetailCard label="Transcript language" value={lecture.processingDetails.transcriptLanguage} />
                <DetailCard label="Number of transcript segments" value={String(lecture.transcript.length)} />
                <DetailCard label="Processing status" value={lecture.processingDetails.processingStatus} />
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

function DetailCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">{label}</div>
      <div className="mt-2 text-sm text-slate-800 dark:text-slate-100">{value}</div>
    </div>
  );
}

function RecentLecturesPage({ lectures, setLectures }: { lectures: LectureProject[]; setLectures: Dispatch<SetStateAction<LectureProject[]>> }) {
  const navigate = useNavigate();

  const handleDelete = (lectureId: string) => {
    const confirmed = window.confirm('Delete this lecture project?');
    if (confirmed) {
      setLectures((current) => current.filter((project) => project.id !== lectureId));
    }
  };

  if (lectures.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
        No lecture records to show.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-700 dark:text-teal-300">Recent lectures</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-50">Project history</h1>
        </div>
      </header>

      <div className="space-y-4">
        {lectures.map((lecture) => (
          <article key={lecture.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{lecture.title}</h2>
                  <StatusBadge status={lecture.status} />
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-300">
                  <span>{lecture.subject}</span>
                  <span className="mx-2">•</span>
                  <span>{lecture.instructor || 'Unspecified instructor'}</span>
                  <span className="mx-2">•</span>
                  <span>{lecture.fileName}</span>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {lecture.status === 'Completed' ? (
                  <button
                    type="button"
                    onClick={() => navigate(`/results/${lecture.id}`)}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500"
                  >
                    Open result
                  </button>
                ) : lecture.status === 'Processing' ? (
                  <button
                    type="button"
                    onClick={() => navigate(`/processing/${lecture.id}`)}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500"
                  >
                    Resume processing
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => navigate(`/processing/${lecture.id}`)}
                    className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-teal-500"
                  >
                    Retry
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => handleDelete(lecture.id)}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  <Trash2 size={15} />
                  Delete
                </button>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: 'Completed' | 'Processing' | 'Failed' }) {
  const tone: StatusTone = status === 'Completed' ? 'completed' : status === 'Processing' ? 'processing' : 'failed';

  const classes = {
    completed: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200',
    processing: 'bg-amber-100 text-amber-800 dark:bg-amber-950/30 dark:text-amber-200',
    failed: 'bg-red-100 text-red-800 dark:bg-red-950/30 dark:text-red-200',
  };

  return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${classes[tone]}`}>{status}</span>;
}

function highlightMatch(text: string, query: string) {
  if (!query.trim()) {
    return text;
  }

  const safePattern = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${safePattern})`, 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200 text-slate-900 dark:bg-yellow-300 dark:text-slate-900">$1</mark>');
}

export default App;
