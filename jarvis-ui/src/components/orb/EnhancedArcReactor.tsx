import { useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { Float, Ring, Sphere } from '@react-three/drei'
import * as THREE from 'three'
import { useVoiceStore, VoiceState } from '../../stores/voiceStore'

// Animated ring component
function AnimatedRing({
  radius,
  thickness,
  rotationSpeed,
  rotationAxis,
  opacity,
  state,
}: {
  radius: number
  thickness: number
  rotationSpeed: number
  rotationAxis: [number, number, number]
  opacity: number
  state: VoiceState
}) {
  const ref = useRef<THREE.Mesh>(null)
  const speed = state === 'listening' ? rotationSpeed * 3 : state === 'speaking' ? rotationSpeed * 2 : rotationSpeed

  useFrame((_, delta) => {
    if (ref.current) {
      ref.current.rotation.x += delta * speed * rotationAxis[0]
      ref.current.rotation.y += delta * speed * rotationAxis[1]
      ref.current.rotation.z += delta * speed * rotationAxis[2]
    }
  })

  return (
    <Ring ref={ref} args={[radius, radius + thickness, 64]}>
      <meshBasicMaterial
        color="#00d4ff"
        transparent
        opacity={opacity}
        side={THREE.DoubleSide}
      />
    </Ring>
  )
}

// Central pulsing core
function PulsingCore({ state }: { state: VoiceState }) {
  const ref = useRef<THREE.Mesh>(null)
  const intensity = state === 'listening' ? 1.5 : state === 'speaking' ? 1.3 : 1

  useFrame(() => {
    if (ref.current) {
      const pulse = 1 + Math.sin(Date.now() * 0.004 * intensity) * 0.1
      ref.current.scale.setScalar(pulse)
    }
  })

  return (
    <Sphere ref={ref} args={[0.3, 32, 32]}>
      <meshBasicMaterial
        color={state === 'listening' ? '#00ffff' : state === 'speaking' ? '#40ffff' : '#00d4ff'}
        transparent
        opacity={0.9}
      />
    </Sphere>
  )
}

// Energy particles orbiting
function OrbitalParticles({ state }: { state: VoiceState }) {
  const ref = useRef<THREE.Points>(null)
  const count = 200

  const positions = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    const r = 0.8 + Math.random() * 0.6
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
    positions[i * 3 + 2] = r * Math.cos(phi)
  }

  useFrame((_, delta) => {
    if (ref.current) {
      const speed = state === 'listening' ? 0.5 : state === 'speaking' ? 0.3 : 0.1
      ref.current.rotation.y += delta * speed
      ref.current.rotation.x += delta * speed * 0.3
    }
  })

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.02}
        color="#00d4ff"
        transparent
        opacity={state === 'idle' ? 0.4 : 0.7}
        sizeAttenuation
      />
    </points>
  )
}

// Arc segments (like Iron Man's reactor)
function ArcSegments({ state }: { state: VoiceState }) {
  const groupRef = useRef<THREE.Group>(null)
  const segments = 8

  useFrame((_, delta) => {
    if (groupRef.current) {
      const speed = state === 'listening' ? 0.8 : state === 'speaking' ? 0.5 : 0.2
      groupRef.current.rotation.z += delta * speed
    }
  })

  return (
    <group ref={groupRef}>
      {Array.from({ length: segments }).map((_, i) => {
        const angle = (i / segments) * Math.PI * 2
        const gap = 0.15
        const startAngle = angle + gap
        const endAngle = angle + (Math.PI * 2 / segments) - gap

        return (
          <mesh key={i} rotation={[Math.PI / 2, 0, 0]}>
            <ringGeometry args={[0.55, 0.6, 32, 1, startAngle, endAngle - startAngle]} />
            <meshBasicMaterial
              color="#00d4ff"
              transparent
              opacity={0.7}
              side={THREE.DoubleSide}
            />
          </mesh>
        )
      })}
    </group>
  )
}

// Outer glow sphere
function GlowSphere({ state }: { state: VoiceState }) {
  const ref = useRef<THREE.Mesh>(null)

  useFrame(() => {
    if (ref.current) {
      const pulse = 1 + Math.sin(Date.now() * 0.002) * 0.05
      const scale = state === 'listening' ? 1.8 : state === 'speaking' ? 1.6 : 1.4
      ref.current.scale.setScalar(scale * pulse)
    }
  })

  return (
    <Sphere ref={ref} args={[1, 32, 32]}>
      <meshBasicMaterial
        color="#00d4ff"
        transparent
        opacity={state === 'idle' ? 0.03 : 0.08}
      />
    </Sphere>
  )
}

// Main scene
function ReactorScene() {
  const { state } = useVoiceStore()

  return (
    <>
      <ambientLight intensity={0.1} />
      <pointLight position={[0, 0, 5]} intensity={1} color="#00d4ff" />

      <Float speed={1.5} rotationIntensity={0.1} floatIntensity={0.3}>
        <group>
          {/* Outer glow */}
          <GlowSphere state={state} />

          {/* Multiple rotating rings */}
          <AnimatedRing radius={1.0} thickness={0.02} rotationSpeed={0.3} rotationAxis={[0, 1, 0]} opacity={0.3} state={state} />
          <AnimatedRing radius={0.85} thickness={0.02} rotationSpeed={-0.4} rotationAxis={[1, 0, 0]} opacity={0.4} state={state} />
          <AnimatedRing radius={0.7} thickness={0.03} rotationSpeed={0.5} rotationAxis={[0.5, 0.5, 0]} opacity={0.5} state={state} />

          {/* Arc segments */}
          <ArcSegments state={state} />

          {/* Inner ring */}
          <Ring args={[0.4, 0.45, 64]} rotation={[Math.PI / 2, 0, 0]}>
            <meshBasicMaterial color="#00ffff" transparent opacity={0.8} side={THREE.DoubleSide} />
          </Ring>

          {/* Core */}
          <PulsingCore state={state} />

          {/* Particles */}
          <OrbitalParticles state={state} />
        </group>
      </Float>
    </>
  )
}

// Exported component
export function EnhancedArcReactor({ className = '' }: { className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <Canvas camera={{ position: [0, 0, 3], fov: 50 }} style={{ background: 'transparent' }}>
        <ReactorScene />
      </Canvas>

      {/* CSS glow layers */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(0, 212, 255, 0.2) 0%, transparent 40%)',
        }}
      />
      <div
        className="absolute inset-0 pointer-events-none animate-pulse"
        style={{
          background: 'radial-gradient(circle, rgba(0, 255, 255, 0.1) 0%, transparent 30%)',
        }}
      />
    </div>
  )
}
