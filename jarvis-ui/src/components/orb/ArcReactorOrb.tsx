import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, Sphere, Ring } from '@react-three/drei'
import * as THREE from 'three'
import { useVoiceStore, VoiceState } from '../../stores/voiceStore'

// Inner core sphere
function CoreSphere({ state }: { state: VoiceState }) {
  const meshRef = useRef<THREE.Mesh>(null)

  const intensity = state === 'listening' ? 1.5 : state === 'speaking' ? 1.2 : 0.8

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.5
      const scale = 1 + Math.sin(Date.now() * 0.003) * 0.05 * intensity
      meshRef.current.scale.setScalar(scale)
    }
  })

  return (
    <Sphere ref={meshRef} args={[0.5, 32, 32]}>
      <meshBasicMaterial
        color={state === 'listening' ? '#00ffff' : '#00d4ff'}
        transparent
        opacity={0.6 * intensity}
      />
    </Sphere>
  )
}

// Glowing concentric rings
function GlowingRings({ state }: { state: VoiceState }) {
  const group = useRef<THREE.Group>(null)
  const ringCount = 3

  const rotationSpeed = state === 'listening' ? 2 : state === 'processing' ? 3 : 0.5

  useFrame((_, delta) => {
    if (group.current) {
      group.current.rotation.z += delta * rotationSpeed * 0.3
      group.current.rotation.x += delta * rotationSpeed * 0.1
    }
  })

  return (
    <group ref={group}>
      {Array.from({ length: ringCount }).map((_, i) => (
        <Ring
          key={i}
          args={[0.7 + i * 0.25, 0.72 + i * 0.25, 64]}
          rotation={[Math.PI / 2, 0, (i * Math.PI) / ringCount]}
        >
          <meshBasicMaterial
            color="#00d4ff"
            transparent
            opacity={0.4 - i * 0.1}
            side={THREE.DoubleSide}
          />
        </Ring>
      ))}
    </group>
  )
}

// Floating particles
function Particles({ state }: { state: VoiceState }) {
  const pointsRef = useRef<THREE.Points>(null)
  const count = 100

  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      const r = 1.2 + Math.random() * 0.5
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      pos[i * 3 + 2] = r * Math.cos(phi)
    }
    return pos
  }, [])

  useFrame((_, delta) => {
    if (pointsRef.current) {
      pointsRef.current.rotation.y += delta * 0.2
      if (state === 'speaking') {
        pointsRef.current.rotation.x += delta * 0.1
      }
    }
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.03}
        color="#00d4ff"
        transparent
        opacity={state === 'idle' ? 0.3 : 0.6}
        sizeAttenuation
      />
    </points>
  )
}

// Outer glow effect
function OuterGlow({ state }: { state: VoiceState }) {
  const meshRef = useRef<THREE.Mesh>(null)

  const baseScale = state === 'listening' ? 2.2 : state === 'speaking' ? 2.0 : 1.8

  useFrame(() => {
    if (meshRef.current) {
      const pulse = 1 + Math.sin(Date.now() * 0.002) * 0.1
      meshRef.current.scale.setScalar(baseScale * pulse)
    }
  })

  return (
    <Sphere ref={meshRef} args={[1, 32, 32]}>
      <meshBasicMaterial
        color="#00d4ff"
        transparent
        opacity={state === 'idle' ? 0.05 : 0.1}
      />
    </Sphere>
  )
}

// Main orb scene
function OrbScene() {
  const { state } = useVoiceStore()

  return (
    <>
      <ambientLight intensity={0.2} />
      <pointLight position={[0, 0, 5]} intensity={1} color="#00d4ff" />

      <Float speed={2} rotationIntensity={0.2} floatIntensity={0.5}>
        <group>
          <OuterGlow state={state} />
          <GlowingRings state={state} />
          <CoreSphere state={state} />
          <Particles state={state} />
        </group>
      </Float>
    </>
  )
}

// Exported component
export function ArcReactorOrb({ className = '' }: { className?: string }) {
  return (
    <div className={`relative ${className}`}>
      {/* Canvas for 3D */}
      <Canvas
        camera={{ position: [0, 0, 4], fov: 50 }}
        style={{ background: 'transparent' }}
      >
        <OrbScene />
      </Canvas>

      {/* CSS glow overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(0, 212, 255, 0.15) 0%, transparent 50%)',
        }}
      />
    </div>
  )
}
