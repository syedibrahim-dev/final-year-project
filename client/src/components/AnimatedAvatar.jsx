/**
 * Animated Avatar Component — AI Customer persona with dynamic expressions.
 *
 * Expressions are driven by trained classifier outputs:
 *   - Emotion (C3) -> facial expression (eyes, mouth, eyebrows)
 *   - Sales State (C5) -> body posture/gesture
 *   - Risk Level (LSTM) -> background ring color
 *   - Voice State -> speaking/listening animation
 *
 * Features:
 *   - SVG with gradients & shading for depth
 *   - Idle breathing animation (subtle scale oscillation)
 *   - Smooth eye tracking (pupils drift toward speaker)
 *   - Multi-frame mouth shapes for speaking (not just open/close)
 *   - Eyebrow + cheek flush for emotions
 *   - Ear + jaw structure for realism
 *
 * Pure CSS/SVG animation — zero GPU cost, ~60fps.
 */

import { useState, useEffect, useRef } from 'react';

// ── Classifier output maps ───────────────────────────────────────────

const EXPRESSION_MAP = {
  positive: 'happy',
  empathetic: 'happy',
  neutral: 'neutral',
  negative: 'concerned',
  anxious: 'worried',
  consultative: 'neutral',
  urgent: 'serious',
  demanding: 'serious',
};

const STATE_POSTURE = {
  interest: 'leaning-in',
  trust: 'open',
  evaluation: 'thinking',
  objection: 'arms-crossed',
  decision: 'leaning-in',
  drop_off_risk: 'pulling-away',
};

const RISK_GLOW = {
  low: '#10b981',
  medium: '#f59e0b',
  high: '#ef4444',
};

// ── Mouth shapes for talking (viseme-lite) ───────────────────────────
const MOUTH_SHAPES = [
  // closed
  (cx, cy) => `M${cx - 8} ${cy} Q${cx} ${cy + 2} ${cx + 8} ${cy}`,
  // slightly open
  (cx, cy) => `M${cx - 7} ${cy - 1} Q${cx} ${cy + 5} ${cx + 7} ${cy - 1}`,
  // wide open
  (cx, cy) => `M${cx - 8} ${cy - 2} Q${cx} ${cy + 7} ${cx + 8} ${cy - 2}`,
  // 'O' shape
  (cx, cy) => `M${cx - 5} ${cy - 2} Q${cx - 6} ${cy + 5} ${cx} ${cy + 6} Q${cx + 6} ${cy + 5} ${cx + 5} ${cy - 2} Q${cx} ${cy - 3} ${cx - 5} ${cy - 2}`,
];

export default function AnimatedAvatar({
  isTyping = false,
  isSpeaking = false,
  isListening = false,
  emotion = 'neutral',
  salesState = 'interest',
  riskLevel = 'low',
  personaName = 'AI Customer',
  difficulty = 'intermediate',
}) {
  const [blinking, setBlinking] = useState(false);
  const [mouthIndex, setMouthIndex] = useState(0);
  const [breathScale, setBreathScale] = useState(1);
  const [pupilOffset, setPupilOffset] = useState({ x: 0, y: 0 });
  const blinkTimer = useRef(null);
  const talkTimer = useRef(null);
  const breathTimer = useRef(null);
  const pupilTimer = useRef(null);

  // ── Random blinking (natural cadence) ──
  useEffect(() => {
    const scheduleBlink = () => {
      const delay = 2000 + Math.random() * 3000;
      blinkTimer.current = setTimeout(() => {
        setBlinking(true);
        setTimeout(() => setBlinking(false), 120);
        scheduleBlink();
      }, delay);
    };
    scheduleBlink();
    return () => clearTimeout(blinkTimer.current);
  }, []);

  // ── Mouth animation when speaking (cycles through shapes) ──
  useEffect(() => {
    if (isTyping || isSpeaking) {
      let frame = 0;
      talkTimer.current = setInterval(() => {
        // Cycle through mouth shapes pseudo-randomly
        frame++;
        const idx = frame % 2 === 0 ? (1 + Math.floor(Math.random() * 3)) : 0;
        setMouthIndex(idx);
      }, 140 + Math.random() * 80);
    } else {
      setMouthIndex(0);
      clearInterval(talkTimer.current);
    }
    return () => clearInterval(talkTimer.current);
  }, [isTyping, isSpeaking]);

  // ── Idle breathing (subtle scale oscillation) ──
  useEffect(() => {
    let phase = 0;
    breathTimer.current = setInterval(() => {
      phase += 0.08;
      setBreathScale(1 + Math.sin(phase) * 0.008);
    }, 50);
    return () => clearInterval(breathTimer.current);
  }, []);

  // ── Pupil drift (eyes track toward speaker / wander when idle) ──
  useEffect(() => {
    const drift = () => {
      if (isListening) {
        // Look at user (slight downward-center)
        setPupilOffset({ x: 0, y: 1 });
      } else if (isTyping || isSpeaking) {
        // Look slightly away while thinking/speaking
        setPupilOffset({ x: -0.5 + Math.random(), y: -0.5 + Math.random() * 0.5 });
      } else {
        // Idle — gentle random drift
        setPupilOffset({ x: (Math.random() - 0.5) * 2, y: (Math.random() - 0.5) * 1.5 });
      }
    };
    drift();
    pupilTimer.current = setInterval(drift, 1800 + Math.random() * 1200);
    return () => clearInterval(pupilTimer.current);
  }, [isListening, isTyping, isSpeaking]);

  // ── Derived state ──
  const expression = EXPRESSION_MAP[emotion] || 'neutral';
  const posture = STATE_POSTURE[salesState] || 'open';
  const glowColor = RISK_GLOW[riskLevel] || RISK_GLOW.low;

  // Expression params
  const eyebrowY = expression === 'worried' ? -3 : expression === 'concerned' ? -1.5 : expression === 'happy' ? -2 : 0;
  const eyebrowAngle = expression === 'worried' ? 10 : expression === 'concerned' ? 6 : expression === 'happy' ? -3 : 0;
  const mouthCurve = expression === 'happy' ? 5 : expression === 'concerned' ? -3 : expression === 'worried' ? -5 : expression === 'serious' ? -1 : 1.5;
  const cheekFlush = expression === 'happy' ? 0.15 : 0;

  // Posture
  const bodyTransform =
    posture === 'leaning-in' ? 'translateY(-3px)' :
    posture === 'pulling-away' ? 'translateY(4px) scale(0.96)' :
    posture === 'arms-crossed' ? 'translateY(1px)' :
    posture === 'thinking' ? 'translateX(3px) rotate(2deg)' :
    'none';

  // Appearance by difficulty
  const skinBase = difficulty === 'advanced' ? '#c4956a' : difficulty === 'beginner' ? '#f0c8a0' : '#dba878';
  const skinShadow = difficulty === 'advanced' ? '#a87d55' : difficulty === 'beginner' ? '#dbb08a' : '#c09060';
  const hairColor = difficulty === 'advanced' ? '#2d1b0e' : difficulty === 'beginner' ? '#8b6f47' : '#4a3520';
  const shirtColor = posture === 'arms-crossed' ? '#475569' : '#5b6b82';
  const shirtHighlight = posture === 'arms-crossed' ? '#546378' : '#6b7d95';

  const mouthCx = 60, mouthCy = 83;

  return (
    <div className="relative flex flex-col items-center">
      {/* Risk glow ring */}
      <div
        className="absolute rounded-full transition-all duration-1000"
        style={{
          inset: '-8px',
          background: `radial-gradient(circle, ${glowColor}30 0%, ${glowColor}10 50%, transparent 70%)`,
          filter: 'blur(8px)',
        }}
      />

      {/* Avatar container with breathing + posture */}
      <div
        className="relative transition-transform duration-700 ease-out"
        style={{ transform: `${bodyTransform} scale(${breathScale})` }}
      >
        <svg viewBox="0 0 120 150" className="w-24 h-28 drop-shadow-lg">
          <defs>
            {/* Skin gradient */}
            <radialGradient id="skinGrad" cx="45%" cy="35%" r="60%">
              <stop offset="0%" stopColor={skinBase} />
              <stop offset="100%" stopColor={skinShadow} />
            </radialGradient>
            {/* Hair gradient */}
            <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={hairColor} />
              <stop offset="100%" stopColor={`${hairColor}cc`} />
            </linearGradient>
            {/* Shirt gradient */}
            <linearGradient id="shirtGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={shirtHighlight} />
              <stop offset="100%" stopColor={shirtColor} />
            </linearGradient>
            {/* Shadow under head */}
            <radialGradient id="neckShadow" cx="50%" cy="0%" r="80%">
              <stop offset="0%" stopColor="#00000018" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
          </defs>

          {/* ── Body / Shoulders ── */}
          <ellipse cx="60" cy="138" rx="42" ry="20" fill="url(#shirtGrad)" />
          {/* Collar */}
          <path d="M48 125 L60 132 L72 125" fill="none" stroke={shirtHighlight} strokeWidth="1.5" opacity="0.6" />

          {/* ── Neck ── */}
          <rect x="51" y="103" width="18" height="16" rx="5" fill="url(#skinGrad)" />
          {/* Neck shadow */}
          <ellipse cx="60" cy="106" rx="12" ry="4" fill="url(#neckShadow)" />

          {/* ── Head ── */}
          <ellipse cx="60" cy="62" rx="36" ry="44" fill="url(#skinGrad)" />

          {/* ── Ears ── */}
          <ellipse cx="24" cy="65" rx="5" ry="8" fill={skinBase} />
          <ellipse cx="24" cy="65" rx="3" ry="5.5" fill={skinShadow} opacity="0.4" />
          <ellipse cx="96" cy="65" rx="5" ry="8" fill={skinBase} />
          <ellipse cx="96" cy="65" rx="3" ry="5.5" fill={skinShadow} opacity="0.4" />

          {/* ── Hair ── */}
          <ellipse cx="60" cy="32" rx="38" ry="26" fill="url(#hairGrad)" />
          <path d="M22 40 Q30 52 28 65" fill={hairColor} opacity="0.6" />
          <path d="M98 40 Q90 52 92 65" fill={hairColor} opacity="0.6" />
          {/* Hair shine */}
          <ellipse cx="48" cy="24" rx="14" ry="6" fill="white" opacity="0.06" />

          {/* ── Eyebrows + Eyes ── */}
          {[
            { cx: 44, browX1: 36, browX2: 52 },   // left
            { cx: 76, browX1: 68, browX2: 84 },    // right
          ].map((eye, i) => (
            <g key={i} style={{ transition: 'transform 0.3s ease' }}
               transform={`translate(0, ${eyebrowY})`}>
              {/* Eyebrow */}
              <path
                d={`M${eye.browX1} ${53 - (i === 0 ? eyebrowAngle : -eyebrowAngle) * 0.3} Q${eye.cx} ${51} ${eye.browX2} ${53 + (i === 0 ? eyebrowAngle : -eyebrowAngle) * 0.3}`}
                fill="none"
                stroke={hairColor}
                strokeWidth="2.5"
                strokeLinecap="round"
                style={{ transition: 'all 0.4s ease' }}
              />
              {/* Eye socket shadow */}
              <ellipse cx={eye.cx} cy="61" rx="8" ry="7" fill="#00000008" />
              {/* Eye */}
              {blinking ? (
                <path
                  d={`M${eye.cx - 6} 62 Q${eye.cx} 60 ${eye.cx + 6} 62`}
                  fill="none" stroke="#1e293b" strokeWidth="2" strokeLinecap="round"
                />
              ) : (
                <>
                  {/* Sclera */}
                  <ellipse cx={eye.cx} cy="61" rx="7" ry="7.5" fill="white" />
                  <ellipse cx={eye.cx} cy="61" rx="7" ry="7.5" fill="none" stroke="#c8b8a8" strokeWidth="0.5" />
                  {/* Iris */}
                  <circle
                    cx={eye.cx + pupilOffset.x}
                    cy={61 + pupilOffset.y}
                    r="4.5"
                    fill="#5a4030"
                    style={{ transition: 'cx 0.6s ease, cy 0.6s ease' }}
                  />
                  {/* Pupil */}
                  <circle
                    cx={eye.cx + pupilOffset.x}
                    cy={61 + pupilOffset.y}
                    r="2.5"
                    fill="#1e1510"
                    style={{ transition: 'cx 0.6s ease, cy 0.6s ease' }}
                  />
                  {/* Highlight */}
                  <circle cx={eye.cx + pupilOffset.x + 1.5} cy={59 + pupilOffset.y} r="1.5" fill="white" opacity="0.9" />
                  <circle cx={eye.cx + pupilOffset.x - 1} cy={62 + pupilOffset.y} r="0.7" fill="white" opacity="0.4" />
                  {/* Upper eyelid line */}
                  <path
                    d={`M${eye.cx - 7} 58 Q${eye.cx} 54 ${eye.cx + 7} 58`}
                    fill="none" stroke="#8b7b6b" strokeWidth="1.2"
                  />
                </>
              )}
            </g>
          ))}

          {/* ── Nose ── */}
          <path d="M58 70 Q59 76 56 78" fill="none" stroke={skinShadow} strokeWidth="1.2" opacity="0.5" />
          <path d="M56 78 Q60 80 64 78" fill="none" stroke={skinShadow} strokeWidth="1" opacity="0.35" />

          {/* ── Cheeks (blush on happy) ── */}
          {cheekFlush > 0 && (
            <>
              <circle cx="36" cy="74" r="7" fill="#e8868640" opacity={cheekFlush} />
              <circle cx="84" cy="74" r="7" fill="#e8868640" opacity={cheekFlush} />
            </>
          )}

          {/* ── Mouth ── */}
          {(isTyping || isSpeaking) ? (
            // Speaking: animated mouth shapes
            <path
              d={MOUTH_SHAPES[mouthIndex](mouthCx, mouthCy)}
              fill={mouthIndex >= 2 ? '#b03a2e' : 'none'}
              stroke={mouthIndex >= 2 ? '#8b2e22' : '#8b5e3c'}
              strokeWidth={mouthIndex >= 2 ? '0.5' : '2'}
              strokeLinecap="round"
              style={{ transition: 'all 0.08s ease' }}
            />
          ) : (
            // Resting expression
            <path
              d={`M${mouthCx - 9} ${mouthCy} Q${mouthCx} ${mouthCy + mouthCurve} ${mouthCx + 9} ${mouthCy}`}
              fill="none"
              stroke="#8b5e3c"
              strokeWidth="2"
              strokeLinecap="round"
              style={{ transition: 'all 0.5s ease' }}
            />
          )}

          {/* ── Chin shadow ── */}
          <ellipse cx="60" cy="96" rx="18" ry="5" fill="#00000006" />

          {/* ── Thinking bubbles ── */}
          {posture === 'thinking' && !isTyping && (
            <g opacity="0.5">
              <circle cx="98" cy="38" r="3.5" fill="#94a3b8" className="animate-pulse" />
              <circle cx="106" cy="30" r="2.5" fill="#94a3b8" className="animate-pulse" style={{ animationDelay: '200ms' }} />
              <circle cx="112" cy="23" r="1.8" fill="#94a3b8" className="animate-pulse" style={{ animationDelay: '400ms' }} />
            </g>
          )}

          {/* ── Arms crossed ── */}
          {posture === 'arms-crossed' && (
            <g opacity="0.7">
              <path d="M28 128 Q48 118 62 130" fill="none" stroke={skinBase} strokeWidth="7" strokeLinecap="round" />
              <path d="M92 128 Q72 118 58 130" fill="none" stroke={skinBase} strokeWidth="7" strokeLinecap="round" />
            </g>
          )}
        </svg>

        {/* ── Listening indicator (audio bars) ── */}
        {isListening && (
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex items-end space-x-[3px]">
            {[3, 4.5, 2.5, 5, 3.5].map((h, i) => (
              <div
                key={i}
                className="w-[3px] bg-emerald-400 rounded-full"
                style={{
                  height: `${h * 2.5}px`,
                  animation: `soundbar 0.6s ease-in-out ${i * 0.08}s infinite alternate`,
                }}
              />
            ))}
          </div>
        )}
      </div>

      {/* State label */}
      <div className="mt-2 text-center">
        <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">
          {salesState?.replace('_', ' ')}
        </span>
      </div>

      {/* Soundbar keyframes (injected once) */}
      <style>{`
        @keyframes soundbar {
          0% { transform: scaleY(0.4); }
          100% { transform: scaleY(1); }
        }
      `}</style>
    </div>
  );
}
