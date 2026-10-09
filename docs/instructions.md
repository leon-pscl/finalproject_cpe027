PROJECT: DSP-Aided Lecture Transcription and Note Generation Web Application
ITERATION: Version 0.1 — Responsive Mock UI and Mock Functions

OBJECTIVE

Build the initial frontend prototype of a browser-based lecture transcription application.

The application must demonstrate this workflow:

Lecture audio file
→ DSP audio enhancement
→ ASR transcription
→ Transcript processing
→ RAG-based note generation
→ Structured lecture notes

This iteration is strictly a UI and interaction prototype. Do not implement actual DSP algorithms, ASR models, embeddings, vector databases, LLM APIs, authentication, cloud storage, or backend processing yet.

Use mock services and realistic demonstration data, but structure the application so that real APIs can replace the mocks in later iterations.

TECHNOLOGY

If no project stack already exists, use:

- React
- TypeScript
- Vite
- Tailwind CSS
- React Router
- Lucide icons
- Vitest and React Testing Library
- ESLint and Prettier

Avoid unnecessary libraries. Do not use a backend or database in this iteration.

DESIGN DIRECTION

Create a clean academic productivity interface suitable for students.

The visual design should be:

- Professional and restrained
- Primarily neutral, with one teal or blue-green accent
- Easy to understand without instructions
- Optimized for reading transcripts and lecture notes
- Available in light and dark themes
- Free from decorative gradients, glowing elements, oversized headings, and generic AI-dashboard styling

Create a simple custom application logo combining the ideas of an audio waveform and a document.

APPLICATION STRUCTURE

Implement the following main views:

1. Dashboard
2. New transcription
3. Processing
4. Results workspace
5. Recent lectures

Use client-side routing. All data may remain in memory for this iteration.

DASHBOARD

Display:

- Application name and short description
- Primary “Process a lecture” action
- Recent lecture projects
- Status badges such as Completed, Processing, and Failed
- Empty state when no lecture projects exist
- Theme toggle
- Responsive navigation

Do not use meaningless analytics or fabricated performance statistics.

NEW TRANSCRIPTION VIEW

Create an audio-upload workflow with:

- Drag-and-drop upload area
- Browse-files button
- Accepted mock formats: WAV, MP3, and M4A
- File name, type, size, and estimated duration display
- Remove or replace file action
- Lecture title input
- Subject or course input
- Optional instructor input
- Language selector with English as the default
- “Start processing” primary button

Validate the following:

- A file must be selected.
- The selected file must have a supported extension.
- The lecture title must not be empty.
- Validation messages must appear beside the relevant control.
- The submit action must be disabled while required information is missing.

DSP OPTIONS

Include an expandable “Audio enhancement settings” section.

Provide mock controls for:

- Noise reduction
- High-pass filtering
- Loudness normalization
- Voice activity detection
- Silence removal
- Audio segmentation

Use sensible default values, but clearly label these as processing options rather than claiming they are already functional.

Include the following processing presets:

- Automatic
- Quiet room
- Noisy classroom
- Custom

Changing a preset should update the visible DSP controls.

PROCESSING VIEW

After submission, navigate to a processing screen and simulate these stages:

1. Validating audio
2. Standardizing audio format
3. Applying DSP enhancement
4. Detecting speech segments
5. Transcribing speech
6. Cleaning the transcript
7. Indexing transcript chunks
8. Generating lecture notes

Requirements:

- Show the current stage.
- Show completed, active, pending, and failed states.
- Display an overall progress bar.
- Simulate progress using deterministic timers.
- Provide a cancel button.
- Include one controlled way to trigger a mock failure for testing.
- Provide retry and return-to-upload actions after a failure.
- On completion, automatically open the results workspace.

Do not use random results that make testing inconsistent.

RESULTS WORKSPACE

Create a responsive workspace containing:

- Lecture title and metadata
- Mock audio player or playback bar
- Transcript tab
- Notes tab
- Processing-details tab
- Search field
- Export menu
- Editable content mode
- “Regenerate notes” mock action

TRANSCRIPT TAB

Display a realistic mock transcript divided into timestamped segments.

Each segment should contain:

- Start timestamp
- Speaker label, such as Lecturer
- Transcript text
- Edit action
- Copy action
- Low-confidence indicator on selected words or segments

Required interactions:

- Selecting a timestamp should update the mock playback position.
- Searching should highlight matching transcript text.
- Editing should update the transcript in application state.
- Include a toggle for showing or hiding confidence indicators.
- Long transcript content must remain readable and scroll correctly.

NOTES TAB

Generate mock structured notes based on the mock transcript.

Use these sections:

- Lecture overview
- Main topics
- Key concepts
- Definitions
- Important examples
- Summary
- Review questions

Each note item should include a source-reference control that points to one or more transcript timestamps.

When a source reference is selected:

- Switch to the transcript tab.
- Scroll to or highlight the corresponding transcript segment.
- Update the mock audio position.

This interaction is important because it demonstrates traceability between generated notes and lecture evidence.

PROCESSING-DETAILS TAB

Display the selected mock configuration:

- Original file information
- DSP preset
- Enabled DSP operations
- ASR model placeholder
- Transcript language
- Number of transcript segments
- Processing status

Clearly label simulated values as demonstration data.

EXPORT FUNCTIONS

Implement frontend-only mock exports for:

- Plain-text transcript
- Markdown notes
- JSON project data

Use browser-generated Blob downloads. PDF and DOCX export may appear as disabled options labeled “Planned.”

RECENT LECTURES

Display several demonstration lecture records showing different application states:

- Completed lecture
- Processing lecture
- Failed lecture

Users should be able to:

- Open a completed result
- Resume viewing a processing simulation
- Retry a failed project
- Delete a project through a confirmation dialog

Store records only in application memory or seeded mock data. Persistent storage is not required yet.

MOCK SERVICE ARCHITECTURE

Create interfaces that can later be connected to real services:

- AudioService
- DSPService
- TranscriptionService
- RetrievalService
- NoteGenerationService
- ExportService

Suggested functions:

- validateAudio(file)
- inspectAudio(file)
- enhanceAudio(file, dspSettings)
- transcribeAudio(processedAudio, options)
- indexTranscript(transcriptSegments)
- generateNotes(transcriptSegments)
- exportTranscript(format)
- exportNotes(format)

Place mock implementations in a dedicated services/mock directory.

UI components must call these service interfaces instead of placing simulated logic directly inside page components.

MOCK STATE MODEL

Support these workflow states:

- idle
- fileSelected
- validating
- processingDSP
- transcribing
- indexing
- generatingNotes
- completed
- cancelled
- failed

Use a clear state machine or reducer. Prevent impossible transitions, such as opening completed results before mock processing finishes.

RESPONSIVE REQUIREMENTS

Develop mobile-first.

Test at these viewport widths:

- 320 px
- 375 px
- 390 px
- 768 px
- 1024 px
- 1366 px and above

Mobile behavior:

- Use a single-column layout.
- Replace the desktop sidebar with a compact header, drawer, or bottom navigation.
- Stack transcript and note controls.
- Keep the main processing action within easy reach.
- Ensure dialogs fit inside the viewport.
- Do not rely on hover interactions.
- Use at least 44 × 44 px touch areas for primary interactive controls.
- Prevent unintended horizontal page scrolling.

Desktop behavior:

- Use a persistent sidebar or structured top navigation.
- Use available width efficiently without overstretching transcript text.
- The results workspace may use a two-column layout for audio/navigation and content.
- Keep long-form transcript and note text within a comfortable reading width.

ACCESSIBILITY

Target WCAG 2.2 Level AA where applicable.

Requirements:

- Semantic HTML landmarks
- One logical H1 per view
- Proper heading hierarchy
- Keyboard-accessible interactions
- Visible focus indicators
- Associated labels for every input
- Accessible error messages
- Accessible dialogs
- ARIA labels for icon-only buttons
- Sufficient text and control contrast
- No information communicated through color alone
- Reduced-motion support
- Screen-reader announcements for processing-stage changes
- Skip-to-content link
- User zoom must not be disabled

THEME

Implement light and dark themes.

Requirements:

- Follow the operating-system preference initially.
- Include a manual theme toggle.
- Use shared semantic design tokens.
- Verify text and controls in both modes.
- Do not duplicate component styling separately for each theme.

UI STATES

Every major view must include designed states for:

- Initial or empty
- Loading
- Success
- Validation error
- Processing failure
- Cancelled processing
- No search results
- Disabled action

Use skeletons or progress indicators where appropriate.

TESTING

Add tests for at least:

- Required-field validation
- Unsupported file rejection
- DSP preset changes
- Valid state transitions
- Cancellation
- Mock processing completion
- Mock processing failure and retry
- Transcript search
- Transcript editing
- Timestamp-to-transcript navigation
- Transcript-to-note source linking
- Export generation

QUALITY CHECKS

Before completion:

- Run linting.
- Run formatting checks.
- Run tests.
- Verify there are no TypeScript errors.
- Verify keyboard navigation.
- Check light and dark modes.
- Check all required viewport sizes.
- Confirm that the page has no unintended horizontal overflow.
- Confirm that refreshing the prototype does not produce a broken route.
- Remove dead code and console errors.

PROJECT ORGANIZATION

Use a maintainable structure similar to:

src/
├── app/
├── components/
│ ├── audio/
│ ├── common/
│ ├── notes/
│ ├── processing/
│ └── transcript/
├── data/
├── hooks/
├── layouts/
├── pages/
├── services/
│ ├── interfaces/
│ └── mock/
├── state/
├── styles/
├── tests/
├── types/
└── utils/

DELIVERABLES

Provide:

1. Complete runnable frontend project
2. README with installation and run instructions
3. Description of the project structure
4. List of implemented mock functions
5. List of deferred real integrations
6. Test commands
7. Responsive-testing checklist
8. Accessibility-testing checklist
9. Screenshots or a short description of desktop and mobile layouts

NON-GOALS FOR VERSION 0.1

Do not implement:

- Actual DSP processing
- Actual Whisper or another ASR model
- LLM API integration
- Embedding generation
- Vector database integration
- User accounts
- Cloud file storage
- Real-time transcription
- Multi-speaker diarization
- Payment functions
- Administrative dashboards
- Fabricated claims about transcription accuracy

ACCEPTANCE CRITERIA

Version 0.1 is accepted when:

- A user can select a supported audio file.
- A user can enter lecture metadata.
- A user can select mock DSP settings.
- Starting the workflow displays all processing stages.
- The workflow can complete, fail, cancel, and retry.
- Completion opens a results workspace.
- The transcript is searchable and editable.
- Generated notes link back to transcript timestamps.
- TXT, Markdown, and JSON mock exports work.
- The application works at 320 px through desktop widths.
- No essential content or controls are lost on mobile.
- All primary controls are keyboard accessible.
- Automated tests and linting pass.
- Mock services are separated from UI components.
- No real AI or DSP integration is falsely represented as functional.
