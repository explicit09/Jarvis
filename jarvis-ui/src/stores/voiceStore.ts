import { create } from 'zustand'

export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking'

interface VoiceStore {
  state: VoiceState
  isRecording: boolean
  audioLevel: number
  frequencyData: Uint8Array | null

  setState: (state: VoiceState) => void
  setIsRecording: (isRecording: boolean) => void
  setAudioLevel: (level: number) => void
  setFrequencyData: (data: Uint8Array | null) => void
}

export const useVoiceStore = create<VoiceStore>((set) => ({
  state: 'idle',
  isRecording: false,
  audioLevel: 0,
  frequencyData: null,

  setState: (state) => set({ state }),
  setIsRecording: (isRecording) => set({ isRecording }),
  setAudioLevel: (audioLevel) => set({ audioLevel }),
  setFrequencyData: (frequencyData) => set({ frequencyData }),
}))
