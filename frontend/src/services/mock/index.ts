export type WorkflowState =
  | 'idle'
  | 'fileSelected'
  | 'validating'
  | 'processingDSP'
  | 'transcribing'
  | 'indexing'
  | 'generatingNotes'
  | 'completed'
  | 'cancelled'
  | 'failed';

export type DspPreset = 'automatic' | 'quiet-room' | 'noisy-classroom' | 'custom';

export interface DspSettings {
  noiseReduction: boolean;
  highPassFilter: boolean;
  loudnessNormalization: boolean;
  voiceActivityDetection: boolean;
  silenceRemoval: boolean;
  audioSegmentation: boolean;
}

export interface AudioFileInfo {
  name: string;
  type: string;
  size: number;
  estimatedDuration: number;
  extension: string;
}

export interface TranscriptSegment {
  id: string;
  start: number;
  end?: number;
  speaker: string;
  text: string;
  confidence: number;
}

export interface LectureProject {
  id: string;
  title: string;
  subject: string;
  instructor: string;
  language: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  duration: number;
  status: 'Completed' | 'Processing' | 'Failed';
  workflowState: WorkflowState;
  createdAt: string;
  dspPreset: DspPreset;
  dspSettings: DspSettings;
  transcript: TranscriptSegment[];
  notes: NoteEntry[];
  processingDetails: {
    originalFile: string;
    preset: string;
    enabledOperations: string[];
    asrModel: string;
    transcriptLanguage: string;
    segmentCount: number;
    processingStatus: string;
  };
}

export interface NoteEntry {
  id: string;
  section: string;
  title: string;
  description: string;
  references: string[];
}

export interface ProcessingStage {
  id: WorkflowState;
  label: string;
  description: string;
}

export const processingStages: ProcessingStage[] = [
  { id: 'validating', label: 'Validating audio', description: 'Checking file integrity and format' },
  { id: 'processingDSP', label: 'Standardizing audio format', description: 'Normalizing container and sample metadata' },
  { id: 'transcribing', label: 'Applying DSP enhancement', description: 'Modeling cleanup and signal conditioning' },
  { id: 'indexing', label: 'Detecting speech segments', description: 'Separating lecturer and background cues' },
  { id: 'generatingNotes', label: 'Transcribing speech', description: 'Running ASR on cleaned audio stream' },
  { id: 'completed', label: 'Cleaning the transcript', description: 'Formatting punctuation and speaker labels' },
  { id: 'completed', label: 'Indexing transcript chunks', description: 'Embedding and retrieval preparation' },
  { id: 'completed', label: 'Generating lecture notes', description: 'Synthesizing structured summary and references' },
];

export const presetSettings: Record<DspPreset, DspSettings> = {
  automatic: {
    noiseReduction: true,
    highPassFilter: true,
    loudnessNormalization: true,
    voiceActivityDetection: true,
    silenceRemoval: true,
    audioSegmentation: true,
  },
  'quiet-room': {
    noiseReduction: true,
    highPassFilter: true,
    loudnessNormalization: true,
    voiceActivityDetection: true,
    silenceRemoval: false,
    audioSegmentation: false,
  },
  'noisy-classroom': {
    noiseReduction: true,
    highPassFilter: true,
    loudnessNormalization: true,
    voiceActivityDetection: true,
    silenceRemoval: true,
    audioSegmentation: true,
  },
  custom: {
    noiseReduction: false,
    highPassFilter: false,
    loudnessNormalization: false,
    voiceActivityDetection: false,
    silenceRemoval: false,
    audioSegmentation: false,
  },
};

export function getDspSettings(preset: DspPreset): DspSettings {
  return { ...presetSettings[preset] };
}

export function validateAudio(file: File | null): { isValid: boolean; message?: string } {
  if (!file) {
    return { isValid: false, message: 'Please select an audio file.' };
  }

  const supported = ['.wav', '.mp3', '.m4a'];
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (!supported.includes(extension)) {
    return {
      isValid: false,
      message: 'Unsupported file type. Please upload WAV, MP3, or M4A audio.',
    };
  }

  return { isValid: true };
}

export function inspectAudio(file: File | null): AudioFileInfo | null {
  if (!file) {
    return null;
  }

  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  return {
    name: file.name,
    type: file.type || 'audio/mpeg',
    size: file.size,
    estimatedDuration: Math.max(4, Math.round(file.size / 180000)),
    extension,
  };
}

export function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const secs = Math.floor(seconds % 60)
    .toString()
    .padStart(2, '0');
  return `${mins}:${secs}`;
}

export function exportTranscriptAsText(project: LectureProject): string {
  return project.transcript
    .map((segment) => `[${formatTimestamp(segment.start)}] ${segment.speaker}: ${segment.text}`)
    .join('\n');
}

export function exportNotesAsMarkdown(project: LectureProject): string {
  const lines = project.notes.map((note) => {
    const refs = note.references.length ? ` (Sources: ${note.references.join(', ')})` : '';
    return `## ${note.section}: ${note.title}${refs}\n\n${note.description}`;
  });
  return `# ${project.title}\n\n${lines.join('\n\n')}`;
}

export function exportProjectJson(project: LectureProject): string {
  return JSON.stringify(project, null, 2);
}

export function createBlobFromText(content: string, type: string): Blob {
  return new Blob([content], { type });
}

export function buildLectureProject(
  values: {
    title: string;
    subject: string;
    instructor: string;
    language: string;
    file: File;
    dspPreset: DspPreset;
    dspSettings: DspSettings;
  },
): LectureProject {
  const transcript: TranscriptSegment[] = [];
  const enabledOperations = Object.entries(values.dspSettings)
    .filter(([, enabled]) => enabled)
    .map(([key]) => key);

  return {
    id: `lecture-${Date.now()}`,
    title: values.title,
    subject: values.subject,
    instructor: values.instructor,
    language: values.language,
    fileName: values.file.name,
    fileType: values.file.type || 'audio/mp3',
    fileSize: values.file.size,
    duration: 0,
    status: 'Processing',
    workflowState: 'validating',
    createdAt: new Date().toISOString(),
    dspPreset: values.dspPreset,
    dspSettings: values.dspSettings,
    transcript,
    notes: [],
    processingDetails: {
      originalFile: values.file.name,
      preset: values.dspPreset,
      enabledOperations,
      asrModel: 'Whisper (backend)',
      transcriptLanguage: values.language,
      segmentCount: transcript.length,
      processingStatus: 'Queued',
    },
  };
}
