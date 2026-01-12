import { describe, it, expect, beforeEach } from 'vitest'
import { useVoiceStore } from './voiceStore'

describe('voiceStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    useVoiceStore.setState({
      state: 'idle',
      isRecording: false,
      audioLevel: 0,
      frequencyData: null,
    })
  })

  describe('setState', () => {
    it('should set state to idle', () => {
      const { setState } = useVoiceStore.getState()
      setState('idle')
      expect(useVoiceStore.getState().state).toBe('idle')
    })

    it('should set state to listening', () => {
      const { setState } = useVoiceStore.getState()
      setState('listening')
      expect(useVoiceStore.getState().state).toBe('listening')
    })

    it('should set state to processing', () => {
      const { setState } = useVoiceStore.getState()
      setState('processing')
      expect(useVoiceStore.getState().state).toBe('processing')
    })

    it('should set state to speaking', () => {
      const { setState } = useVoiceStore.getState()
      setState('speaking')
      expect(useVoiceStore.getState().state).toBe('speaking')
    })
  })

  describe('setIsRecording', () => {
    it('should set recording to true', () => {
      const { setIsRecording } = useVoiceStore.getState()
      setIsRecording(true)
      expect(useVoiceStore.getState().isRecording).toBe(true)
    })

    it('should set recording to false', () => {
      useVoiceStore.setState({ isRecording: true })
      const { setIsRecording } = useVoiceStore.getState()
      setIsRecording(false)
      expect(useVoiceStore.getState().isRecording).toBe(false)
    })
  })

  describe('setAudioLevel', () => {
    it('should set audio level', () => {
      const { setAudioLevel } = useVoiceStore.getState()
      setAudioLevel(0.75)
      expect(useVoiceStore.getState().audioLevel).toBe(0.75)
    })

    it('should set audio level to zero', () => {
      useVoiceStore.setState({ audioLevel: 0.5 })
      const { setAudioLevel } = useVoiceStore.getState()
      setAudioLevel(0)
      expect(useVoiceStore.getState().audioLevel).toBe(0)
    })

    it('should set audio level to max', () => {
      const { setAudioLevel } = useVoiceStore.getState()
      setAudioLevel(1)
      expect(useVoiceStore.getState().audioLevel).toBe(1)
    })
  })

  describe('setFrequencyData', () => {
    it('should set frequency data', () => {
      const { setFrequencyData } = useVoiceStore.getState()
      const data = new Uint8Array([10, 20, 30, 40])
      setFrequencyData(data)
      expect(useVoiceStore.getState().frequencyData).toBe(data)
    })

    it('should set frequency data to null', () => {
      const data = new Uint8Array([10, 20])
      useVoiceStore.setState({ frequencyData: data })
      const { setFrequencyData } = useVoiceStore.getState()
      setFrequencyData(null)
      expect(useVoiceStore.getState().frequencyData).toBe(null)
    })
  })
})
