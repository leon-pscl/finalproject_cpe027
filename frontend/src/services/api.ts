<<<<<<< HEAD
/// <reference types="vite/client" />

/**
 * Frontend API client for the LectureFlow backend.
 *
 * This client talks to the FastAPI backend through the Vite localhost proxy. It
 * uses opaque bearer tokens only: the operator identity is derived server-side
 * from a verified token, so this module never sends a client-provided user id
 * or owner id.
 */

export type ErrorCode = string;

export type JobStage =
  | 'queued'
  | 'validating'
  | 'extracting'
  | 'preprocessing'
  | 'transcribing'
  | 'indexing'
  | 'generating_notes'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type LectureStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface ErrorResponse {
  detail?: {
    error_code?: ErrorCode;
    message?: string;
    request_id?: string;
  } | string;
}

export interface InitiateUploadRequest {
  title: string;
  declared_type: string;
  declared_size_bytes: number;
}

export interface InitiateUploadResponse {
  lecture_id: string;
  storage_path: string;
  signed_upload_url: string;
  expires_at: string;
}

export interface CompleteUploadRequest {
  storage_path: string;
  observed_size_bytes?: number | null;
  observed_content_type?: string | null;
}

export interface CompleteUploadResponse {
  lecture_id: string;
  job_id: string;
  stage: JobStage;
  message: string;
}

export interface LectureMetadata {
  lecture_id: string;
  owner_id: string;
  title: string;
  storage_path: string;
  duration_s?: number | null;
  media_metadata?: Record<string, unknown>;
  state: LectureStatus;
  active_version?: string | null;
  deleted_at?: string | null;
  created_at: string;
}

export interface UploadProgress {
  loaded: number;
  total: number;
  fraction: number;
  percent: number;
  phase: 'initiating' | 'uploading' | 'completing' | 'polling';
}

export interface UploadLectureResult {
  lectureId: string;
  jobId?: string;
  stage?: JobStage;
  storagePath: string;
  uploadResponse: InitiateUploadResponse;
  completeResponse: CompleteUploadResponse;
  lecture?: LectureMetadata | null;
}

export interface ApiErrorOptions {
  code?: ErrorCode;
  status?: number;
  requestId?: string | null;
  retryable?: boolean;
  details?: unknown;
}

export class ApiError extends Error {
  public readonly code: ErrorCode;
  public readonly status: number;
  public readonly requestId: string | null;
  public readonly retryable: boolean;
  public readonly details: unknown;

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message);
    this.name = 'ApiError';
    this.code = options.code || 'INVALID_REQUEST';
    this.status = options.status ?? 0;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details ?? null;
  }
}

export type AccessTokenProvider = () => string | null | Promise<string | null>;
export interface ApiRequestOptions {
  signal?: AbortSignal;
  headers?: Record<string, string>;
  method?: string;
  body?: BodyInit | null;
  includeAuth?: boolean;
  maxRetries?: number;
}

type RetryableStatus = number;

function isRetryableStatus(status: RetryableStatus): boolean {
  return status === 408 || status === 429 || status >= 500;
}

function normalizePath(path: string): string {
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const withSlash = path.startsWith('/') ? path : `/${path}`;
  return withSlash;
}

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  const value = configured && configured.length > 0 ? configured : '/api';
  return value.replace(/\/+$/, '');
}

export function buildApiUrl(path: string): string {
  const url = normalizePath(path);
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  return `${getApiBaseUrl()}${url}`;
}

let accessTokenProvider: AccessTokenProvider | null = null;
let inMemoryAccessToken: string | null = import.meta.env.DEV
  ? import.meta.env.VITE_API_TOKEN?.trim() || null
  : null;

export function configureAccessTokenProvider(provider: AccessTokenProvider | null): void {
  accessTokenProvider = provider;
}

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token && token.trim() ? token.trim() : null;
}

export function clearAccessToken(): void {
  inMemoryAccessToken = null;
}

export async function getAccessToken(): Promise<string | null> {
  if (accessTokenProvider) {
    try {
      const provided = await accessTokenProvider();
      if (provided && provided.trim()) {
        return provided.trim();
      }
    } catch {
      // A broken token provider should not obscure a valid local development token.
    }
  }

  if (inMemoryAccessToken) {
    return inMemoryAccessToken;
  }

  // Local auth tokens are only available in development. Production applications
  // should configure a token provider that obtains an ID token from the active
  // user session, rather than persisting bearer tokens in frontend storage.
  if (import.meta.env.DEV) {
    try {
      const local =
        window.sessionStorage.getItem('lectureflow.apiAccessToken') ||
        window.localStorage.getItem('lectureflow.apiAccessToken');
      if (local && local.trim()) {
        return local.trim();
      }
    } catch {
      // Storage can be unavailable in private browsing or sandboxed contexts.
    }
    const envToken = import.meta.env.VITE_API_TOKEN?.trim();
    if (envToken) {
      return envToken;
    }
  }

  return null;
}

async function wait(delayMs: number, signal?: AbortSignal): Promise<void> {
  if (delayMs <= 0) {
    return;
  }
  await new Promise<void>((resolve, reject) => {
    const timeout = window.setTimeout(() => resolve(), delayMs);
    if (signal) {
      const onAbort = () => {
        window.clearTimeout(timeout);
        reject(new DOMException('Aborted', 'AbortError'));
      };
      if (signal.aborted) {
        onAbort();
      } else {
        signal.addEventListener('abort', onAbort, { once: true });
      }
    }
  });
}

function parseErrorBody(body: unknown, status: number): {
  code: ErrorCode;
  message: string;
  requestId: string | null;
} {
  if (typeof body === 'string' && body.trim()) {
    return {
      code: status === 401 || status === 403 ? 'AUTH_INVALID' : 'INVALID_REQUEST',
      message: body.trim(),
      requestId: null,
    };
  }

  const payload = body && typeof body === 'object' ? (body as Record<string, unknown>) : {};
  const detail = payload.detail;

  if (detail && typeof detail === 'object') {
    const nested = detail as Record<string, unknown>;
    return {
      code: typeof nested.error_code === 'string' ? nested.error_code : status === 401 ? 'AUTH_REQUIRED' : 'INVALID_REQUEST',
      message: typeof nested.message === 'string' ? nested.message : `Request failed with status ${status}`,
      requestId: typeof nested.request_id === 'string' ? nested.request_id : null,
    };
  }

  if (typeof detail === 'string' && detail.trim()) {
    return {
      code: status === 401 || status === 403 ? 'AUTH_REQUIRED' : 'INVALID_REQUEST',
      message: detail,
      requestId: null,
    };
  }

  if (typeof payload.error_code === 'string' || typeof payload.message === 'string') {
    return {
      code: typeof payload.error_code === 'string' ? payload.error_code : status === 401 ? 'AUTH_REQUIRED' : 'INVALID_REQUEST',
      message: typeof payload.message === 'string' ? payload.message : `Request failed with status ${status}`,
      requestId: typeof payload.request_id === 'string' ? payload.request_id : null,
    };
  }

  return {
    code: status === 401 || status === 403 ? 'AUTH_REQUIRED' : 'INVALID_REQUEST',
    message: `Request failed with status ${status}`,
    requestId: null,
  };
}

export async function requestJson<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const url = buildApiUrl(path);
  const requiresAuth = options.includeAuth !== false;
  const maxRetries = options.maxRetries ?? 2;
  let lastNetworkError: unknown = null;

  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      const token = requiresAuth ? await getAccessToken() : null;
      if (requiresAuth && !token) {
        throw new ApiError('A bearer access token is required for this request.', {
          code: 'AUTH_REQUIRED',
          status: 401,
          retryable: false,
        });
      }

      const headers: Record<string, string> = {
        Accept: 'application/json',
        ...options.headers,
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      if (options.body && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
      }

      const response = await fetch(url, {
        method: options.method ?? 'GET',
        headers,
        body: options.body,
        signal: options.signal,
      });

      let body: unknown = null;
      const rawText = await response.text();
      if (rawText) {
        try {
          body = JSON.parse(rawText);
        } catch {
          body = rawText;
        }
      }

      if (!response.ok) {
        const parsed = parseErrorBody(body, response.status);
        const error = new ApiError(parsed.message, {
          code: parsed.code,
          status: response.status,
          requestId: parsed.requestId,
          retryable: attempt < maxRetries && isRetryableStatus(response.status),
          details: body,
        });

        if (error.retryable) {
          await wait(250 * 2 ** attempt, options.signal);
          continue;
        }
        throw error;
      }

      return body as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }

      if (error instanceof DOMException && error.name === 'AbortError') {
        throw error;
      }

      lastNetworkError = error;
      if (attempt < maxRetries) {
        await wait(250 * 2 ** attempt, options.signal);
        continue;
      }
    }
  }

  throw new ApiError('Unable to reach the LectureFlow API.', {
    code: 'INVALID_REQUEST',
    status: 0,
    retryable: true,
    details: lastNetworkError,
  });
}

export async function initiateUpload(
  request: InitiateUploadRequest,
  options: ApiRequestOptions = {},
): Promise<InitiateUploadResponse> {
  return requestJson<InitiateUploadResponse>('/lectures/uploads', {
    ...options,
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getLecture(
  lectureId: string,
  options: ApiRequestOptions = {},
): Promise<LectureMetadata> {
  return requestJson<LectureMetadata>(`/lectures/${encodeURIComponent(lectureId)}`, {
    ...options,
    method: 'GET',
  });
}

export async function listLectures(
  options: { limit?: number } & ApiRequestOptions = {},
): Promise<LectureMetadata[]> {
  const query = new URLSearchParams();
  if (options.limit !== undefined) {
    query.set('limit', String(options.limit));
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  const { limit, ...requestOptions } = options;
  void limit;
  return requestJson<LectureMetadata[]>(`/lectures${suffix}`, {
    ...requestOptions,
    method: 'GET',
  });
}

export async function completeUpload(
  lectureId: string,
  request: CompleteUploadRequest,
  options: ApiRequestOptions = {},
): Promise<CompleteUploadResponse> {
  return requestJson<CompleteUploadResponse>(
    `/lectures/${encodeURIComponent(lectureId)}/upload-complete`,
    {
      ...options,
      method: 'POST',
      body: JSON.stringify(request),
    },
  );
}

export async function retryUpload(
  lectureId: string,
  options: ApiRequestOptions = {},
): Promise<CompleteUploadResponse> {
  return requestJson<CompleteUploadResponse>(
    `/lectures/${encodeURIComponent(lectureId)}/retry`,
    {
      ...options,
      method: 'POST',
      body: JSON.stringify({}),
    },
  );
}

async function putSignedFile(
  signedUploadUrl: string,
  file: File,
  options: {
    onProgress?: (event: ProgressEvent<EventTarget>) => void;
    signal?: AbortSignal;
    contentType?: string;
    headers?: Record<string, string>;
  },
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', signedUploadUrl, true);
    xhr.setRequestHeader('Content-Type', options.contentType ?? file.type ?? 'application/octet-stream');
    if (options.headers) {
      for (const [name, value] of Object.entries(options.headers)) {
        xhr.setRequestHeader(name, value);
      }
    }

    xhr.upload.onprogress = (event) => {
      options.onProgress?.(event);
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
        return;
      }

      let parsed: unknown = null;
      try {
        parsed = JSON.parse(xhr.responseText);
      } catch {
        parsed = xhr.responseText;
      }

      const error = parseErrorBody(parsed, xhr.status);
      reject(
        new ApiError(error.message, {
          code: error.code,
          status: xhr.status,
          requestId: error.requestId,
          retryable: isRetryableStatus(xhr.status),
          details: parsed,
        }),
      );
    };

    xhr.onerror = () => {
      reject(new TypeError('Network request failed'));
    };
    xhr.onabort = () => reject(new DOMException('Aborted', 'AbortError'));

    if (options.signal) {
      if (options.signal.aborted) {
        reject(new DOMException('Aborted', 'AbortError'));
        return;
      }
      options.signal.addEventListener(
        'abort',
        () => {
          xhr.abort();
        },
        { once: true },
      );
    }

    xhr.send(file);
  });
}

export async function uploadSignedFile(
  signedUploadUrl: string,
  file: File,
  options: {
    onProgress?: (progress: UploadProgress) => void;
    signal?: AbortSignal;
    contentType?: string;
    headers?: Record<string, string>;
    maxRetries?: number;
  } = {},
): Promise<void> {
  const maxRetries = options.maxRetries ?? 2;
  let lastError: unknown = null;

  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    try {
      await putSignedFile(signedUploadUrl, file, {
        onProgress: (event) => {
          options.onProgress?.({
            loaded: event.loaded,
            total: event.total,
            fraction: event.total > 0 ? event.loaded / event.total : 0,
            percent: event.total > 0 ? Math.round((event.loaded / event.total) * 100) : 0,
            phase: 'uploading',
          });
        },
        signal: options.signal,
        contentType: options.contentType ?? (file.type || 'application/octet-stream'),
        headers: options.headers,
      });

      return;
    } catch (error) {
      lastError = error;
      const retryableNetworkError =
        error instanceof TypeError || (error instanceof Error && error.message.includes('NetworkError'));

      if (attempt < maxRetries && retryableNetworkError) {
        await wait(250 * 2 ** attempt, options.signal);
        continue;
      }

      if (error instanceof ApiError) {
        if (attempt < maxRetries && error.retryable) {
          await wait(250 * 2 ** attempt, options.signal);
          continue;
        }
        throw error;
      }

      throw error instanceof Error
        ? error
        : new Error('Signed upload failed.');
    }
  }

  if (lastError instanceof Error) {
    throw lastError;
  }
  throw new Error('Signed upload failed.');
}

export interface UploadLectureRequest {
  title: string;
  file: File;
  declaredType?: string;
  declaredSizeBytes?: number;
  observedContentType?: string | null;
  onProgress?: (progress: UploadProgress) => void;
  signal?: AbortSignal;
}

export async function uploadLecture(
  request: UploadLectureRequest,
  options: ApiRequestOptions = {},
): Promise<UploadLectureResult> {
  const signal = request.signal ?? options.signal;
  const declaredType = request.declaredType ?? request.file.type ?? guessContentType(request.file.name);
  const declaredSizeBytes = request.declaredSizeBytes ?? request.file.size;

  request.onProgress?.({
    loaded: 0,
    total: declaredSizeBytes,
    fraction: 0,
    percent: 0,
    phase: 'initiating',
  });

  const initiated = await initiateUpload(
    {
      title: request.title,
      declared_type: declaredType,
      declared_size_bytes: declaredSizeBytes,
    },
    {
      ...options,
      signal,
    },
  );

  await uploadSignedFile(initiated.signed_upload_url, request.file, {
    onProgress: request.onProgress,
    signal,
    contentType: declaredType,
  });

  request.onProgress?.({
    loaded: declaredSizeBytes,
    total: declaredSizeBytes,
    fraction: 1,
    percent: 100,
    phase: 'completing',
  });

  const completed = await completeUpload(
    initiated.lecture_id,
    {
      storage_path: initiated.storage_path,
      observed_size_bytes: request.file.size,
      observed_content_type: request.observedContentType ?? declaredType,
    },
    { signal, maxRetries: options.maxRetries },
  );

  request.onProgress?.({
    loaded: declaredSizeBytes,
    total: declaredSizeBytes,
    fraction: 1,
    percent: 100,
    phase: 'polling',
  });

  let lecture: LectureMetadata | null = null;
  try {
    lecture = await getLecture(completed.lecture_id, { signal });
  } catch {
    lecture = null;
  }

  return {
    lectureId: initiated.lecture_id,
    jobId: completed.job_id,
    stage: completed.stage,
    storagePath: initiated.storage_path,
    uploadResponse: initiated,
    completeResponse: completed,
    lecture,
  };
}

export async function pollLectureForCompletion(
  lectureId: string,
  options: {
    intervalMs?: number;
    timeoutMs?: number;
    maxDelayMs?: number;
    signal?: AbortSignal;
    onStatus?: (lecture: LectureMetadata) => void;
  } = {},
): Promise<LectureMetadata | null> {
  const intervalMs = options.intervalMs ?? 1000;
  const timeoutMs = options.timeoutMs ?? 30000;
  const maxDelayMs = options.maxDelayMs ?? 5000;
  const deadline = Date.now() + timeoutMs;
  let delay = intervalMs;

  while (!options.signal?.aborted && Date.now() < deadline) {
    let lecture: LectureMetadata | null = null;
    try {
      lecture = await getLecture(lectureId, { signal: options.signal });
    } catch {
      lecture = null;
    }

    if (lecture) {
      options.onStatus?.(lecture);
      if (lecture.state === 'completed' || lecture.state === 'failed' || lecture.state === 'cancelled') {
        return lecture;
      }
    }

    await wait(delay, options.signal);
    delay = Math.min(delay * 2, maxDelayMs);
  }

  return null;
}

export const pollLectureStatus = pollLectureForCompletion;
export const uploadFile = uploadSignedFile;
export const initiateLectureUpload = initiateUpload;
export const completeLectureUpload = completeUpload;
export const fetchLecture = getLecture;

export interface SignedDownloadUrlResponse {
  storage_path: string;
  signed_download_url: string;
  signed_url?: string | null;
  download_url?: string | null;
  expires_at: string;
}

export async function createSignedDownloadUrl(
  storagePath: string,
  options: ApiRequestOptions = {},
): Promise<SignedDownloadUrlResponse> {
  return requestJson<SignedDownloadUrlResponse>(
    `/storage/download-url/${storagePath}`,
    {
      ...options,
      method: 'GET',
    },
  );
}

export async function getSignedDownloadUrl(
  storagePath: string,
  options: ApiRequestOptions = {},
): Promise<SignedDownloadUrlResponse | null> {
  try {
    return await createSignedDownloadUrl(storagePath, options);
  } catch {
    return null;
  }
}

export async function fetchSignedMedia(
  storagePathOrUrl: string,
  options: ApiRequestOptions = {},
): Promise<Blob> {
  const url = /^[a-z]+:/i.test(storagePathOrUrl)
    ? storagePathOrUrl
    : buildApiUrl(`/storage/download/${storagePathOrUrl}`);
  const token = await getAccessToken();
  const response = await fetch(url, {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    signal: options.signal,
  });
  if (!response.ok) {
    throw new ApiError('Unable to read signed storage media.', {
      code: 'INVALID_REQUEST',
      status: response.status,
      retryable: false,
    });
  }
  return response.blob();
}

function guessContentType(fileName: string): string {
  const lower = fileName.toLowerCase();
  if (lower.endsWith('.wav')) {
    return 'audio/wav';
  }
  if (lower.endsWith('.mp3')) {
    return 'audio/mpeg';
  }
  if (lower.endsWith('.m4a')) {
    return 'audio/mp4';
  }
  if (lower.endsWith('.mp4')) {
    return 'video/mp4';
  }
  if (lower.endsWith('.webm')) {
    return 'video/webm';
  }
  if (lower.endsWith('.mov')) {
    return 'video/quicktime';
  }
  return 'application/octet-stream';
}
=======
import type { TranscriptSegment } from './mock';

export type JobStatus = {
  id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number; // 0..1
  language: string | null;
  duration: number;
  segments: Array<{ id: string; start: number; end: number; text: string; confidence: number }>;
  error: string | null;
  phase?: string;
  dsp?: { applied: boolean; snr_est_before_db?: number; snr_est_after_db?: number; speech_ratio?: number; seconds?: number; error?: string | null } | null;
};

async function failure(res: Response): Promise<Error> {
  let detail = `Request failed (${res.status}).`;
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') detail = body.detail;
  } catch {
    /* non-JSON error body */
  }
  return new Error(detail);
}

/** Uploads the recording; the backend transcribes it with a pretrained Whisper model. */
export async function submitTranscription(file: File): Promise<{ id: string }> {
  const body = new FormData();
  body.append('file', file);
  const res = await fetch('/api/transcriptions', { method: 'POST', body });
  if (!res.ok) throw await failure(res);
  return res.json();
}

/** Returns null when the backend no longer knows the job (e.g. it restarted). */
export async function fetchJob(id: string): Promise<JobStatus | null> {
  const res = await fetch(`/api/transcriptions/${encodeURIComponent(id)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw await failure(res);
  return res.json();
}

export async function deleteJob(id: string): Promise<void> {
  try {
    await fetch(`/api/transcriptions/${encodeURIComponent(id)}`, { method: 'DELETE' });
  } catch {
    /* best effort */
  }
}

export const toTranscript = (job: JobStatus): TranscriptSegment[] =>
  job.segments.map((s) => ({ id: s.id, start: s.start, end: s.end, speaker: 'Lecturer', text: s.text, confidence: s.confidence }));
>>>>>>> iteration_lim
