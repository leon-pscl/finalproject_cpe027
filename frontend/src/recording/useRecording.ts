import { useContext } from 'react';
import { RecordingContext, type RecordingContextValue } from './context';

export function useRecording(): RecordingContextValue {
  const value = useContext(RecordingContext);
  if (!value) throw new Error('useRecording must be used inside <RecordingProvider>');
  return value;
}
