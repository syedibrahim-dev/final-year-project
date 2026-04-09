/**
 * Animated Customer Avatar — Cute cartoon style (Memoji-inspired)
 *
 * Driven by classifier outputs:
 *   - Emotion (C3)      -> facial expression (eyes, mouth, brows, cheeks)
 *   - Sales State (C5)  -> head tilt + gesture
 *   - Risk Level (LSTM) -> aura color
 *   - Voice State        -> speaking animation, listening indicator
 *
 * Pure SVG + requestAnimationFrame — silky 60fps, no dependencies, loads instantly.
 */

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

// ── Maps ─────────────────────────────────────────────────────────────

const EXPRESSION_MAP = {
  positive: 'happy', empathetic: 'happy', neutral: 'neutral',
  negative: 'concerned', anxious: 'worried', consultative: 'neutral',
  urgent: 'serious', demanding: 'serious',
};

const RISK_COLORS = { low: '#34d399', medium: '#fbbf24', high: '#f87171' };

// ── Expression hints (emotion + state -> coaching tip) ───────────────

const EMOTION_HINTS = {
  happy:     { icon: '😊', label: 'Engaged', color: '#10b981', desc: 'Customer is receptive and positive' },
  concerned: { icon: '😟', label: 'Concerned', color: '#f59e0b', desc: 'Customer has reservations' },
  worried:   { icon: '😰', label: 'Anxious', color: '#ef4444', desc: 'Customer feels uncertain or pressured' },
  serious:   { icon: '😐', label: 'Guarded', color: '#6b7280', desc: 'Customer is evaluating critically' },
  neutral:   { icon: '🙂', label: 'Neutral', color: '#8b95a5', desc: 'Customer is listening' },
};

const STATE_TIPS = {
  interest:      'Keep building curiosity — ask discovery questions',
  trust:         'Being transparent here strengthens the relationship',
  evaluation:    'Provide clear comparisons and proof points',
  objection:     'Acknowledge their concern before responding',
  decision:      'Summarise value and guide toward next steps',
  drop_off_risk: 'Re-engage with a new angle or ask what changed',
};

// ── Smooth lerp helper ───────────────────────────────────────────────

function lerp(a, b, t) { return a + (b - a) * t; }

export default function AnimatedAvatar3D({
  isTyping = false,
  isSpeaking = false,
  isListening = false,
  emotion = 'neutral',
  salesState = 'interest',
  riskLevel = 'low',
  personaName = 'AI Customer',
  difficulty = 'intermediate',
}) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const stateRef = useRef({
    // Blink
    blinkTimer: 0, nextBlink: 2.5, blinkVal: 0, blinking: false,
    // Mouth
    mouthOpen: 0, talkPhase: 0,
    // Breathing
    breathPhase: 0,
    // Pupil
    pupilX: 0, pupilY: 0, pupilTargetX: 0, pupilTargetY: 0, pupilTimer: 0,
    // Head tilt
    headTilt: 0, headTiltTarget: 0, headNod: 0,
    // Expression blend (smooth transitions)
    browRaise: 0, browFurrow: 0, smile: 0, frown: 0, surprise: 0,
    browRaiseTarget: 0, browFurrowTarget: 0, smileTarget: 0, frownTarget: 0, surpriseTarget: 0,
    // Last time
    lastTime: 0,
  });

  const expression = EXPRESSION_MAP[emotion] || 'neutral';
  const riskColor = RISK_COLORS[riskLevel] || RISK_COLORS.low;

  // Skin/hair by difficulty
  const skin = difficulty === 'advanced' ? '#c4956a' : difficulty === 'beginner' ? '#fad5b5' : '#e8b88a';
  const skinShadow = difficulty === 'advanced' ? '#a87d55' : difficulty === 'beginner' ? '#e8c4a0' : '#d4a070';
  const hair = difficulty === 'advanced' ? '#2d1b0e' : difficulty === 'beginner' ? '#b8935a' : '#5a3825';
  const shirtColor = '#6c7fa0';

  // Update expression targets
  useEffect(() => {
    const s = stateRef.current;
    s.smileTarget = expression === 'happy' ? 1 : 0;
    s.frownTarget = (expression === 'concerned' || expression === 'worried') ? 1 : 0;
    s.browRaiseTarget = (expression === 'worried' || expression === 'happy') ? 1 : 0;
    s.browFurrowTarget = (expression === 'serious' || expression === 'concerned') ? 1 : 0;
    s.surpriseTarget = expression === 'worried' ? 0.5 : 0;
  }, [expression]);

  // Update head tilt from posture
  useEffect(() => {
    const s = stateRef.current;
    switch (salesState) {
      case 'interest': case 'decision': s.headTiltTarget = -4; break;
      case 'evaluation': case 'trust': s.headTiltTarget = 6; break;
      case 'objection': s.headTiltTarget = -2; break;
      case 'drop_off_risk': s.headTiltTarget = 3; break;
      default: s.headTiltTarget = 0;
    }
  }, [salesState]);

  // Update pupil target
  useEffect(() => {
    const s = stateRef.current;
    if (isListening) { s.pupilTargetX = 0; s.pupilTargetY = 2; }
    else if (isTyping || isSpeaking) { s.pupilTargetX = -1; s.pupilTargetY = -1; }
    else { s.pupilTargetX = (Math.random() - 0.5) * 4; s.pupilTargetY = (Math.random() - 0.5) * 3; }
  }, [isListening, isTyping, isSpeaking]);

  // Animation loop
  const draw = useCallback((timestamp) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const cx = W / 2;
    const s = stateRef.current;

    const dt = s.lastTime ? Math.min((timestamp - s.lastTime) / 1000, 0.05) : 0.016;
    s.lastTime = timestamp;

    // ── Update animation state ──
    s.breathPhase += dt * 1.8;
    const breathY = Math.sin(s.breathPhase) * 1.5;

    // Blink
    s.blinkTimer += dt;
    if (!s.blinking && s.blinkTimer > s.nextBlink) {
      s.blinking = true; s.blinkVal = 0; s.blinkTimer = 0;
      s.nextBlink = 2 + Math.random() * 3;
    }
    if (s.blinking) {
      s.blinkVal += dt * 12;
      if (s.blinkVal > 2) { s.blinking = false; s.blinkVal = 0; }
    }
    const eyeClose = s.blinking ? (s.blinkVal < 1 ? s.blinkVal : Math.max(0, 2 - s.blinkVal)) : 0;

    // Mouth
    if (isTyping || isSpeaking) {
      s.talkPhase += dt * 10;
      s.mouthOpen = lerp(s.mouthOpen, 0.4 + Math.abs(Math.sin(s.talkPhase * 1.7)) * 0.4 + Math.abs(Math.sin(s.talkPhase * 2.9)) * 0.2, dt * 15);
    } else {
      s.mouthOpen = lerp(s.mouthOpen, 0, dt * 8);
    }

    // Head tilt
    s.headTilt = lerp(s.headTilt, s.headTiltTarget, dt * 3);
    if (isTyping || isSpeaking) {
      s.headNod = Math.sin(s.talkPhase * 0.4) * 1.5;
    } else {
      s.headNod = lerp(s.headNod, 0, dt * 3);
    }

    // Pupil
    s.pupilTimer += dt;
    if (s.pupilTimer > 2) {
      s.pupilTimer = 0;
      if (!isListening && !isTyping && !isSpeaking) {
        s.pupilTargetX = (Math.random() - 0.5) * 4;
        s.pupilTargetY = (Math.random() - 0.5) * 3;
      }
    }
    s.pupilX = lerp(s.pupilX, s.pupilTargetX, dt * 4);
    s.pupilY = lerp(s.pupilY, s.pupilTargetY, dt * 4);

    // Expression blend
    s.smile = lerp(s.smile, s.smileTarget, dt * 4);
    s.frown = lerp(s.frown, s.frownTarget, dt * 4);
    s.browRaise = lerp(s.browRaise, s.browRaiseTarget, dt * 4);
    s.browFurrow = lerp(s.browFurrow, s.browFurrowTarget, dt * 4);
    s.surprise = lerp(s.surprise, s.surpriseTarget, dt * 4);

    // ── Clear ──
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    ctx.translate(0, breathY);

    // Overall head rotation
    const tiltRad = (s.headTilt + s.headNod) * Math.PI / 180;
    ctx.save();
    ctx.translate(cx, 155);
    ctx.rotate(tiltRad);
    ctx.translate(-cx, -155);

    // ── Risk aura ──
    const auraGrad = ctx.createRadialGradient(cx, 130, 40, cx, 130, 130);
    auraGrad.addColorStop(0, riskColor + '20');
    auraGrad.addColorStop(0.6, riskColor + '08');
    auraGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = auraGrad;
    ctx.fillRect(0, 0, W, H);

    // ── Body / Shoulders ──
    ctx.fillStyle = shirtColor;
    ctx.beginPath();
    ctx.ellipse(cx, 270, 75, 35, 0, 0, Math.PI, true);
    ctx.fill();

    // Collar
    ctx.fillStyle = '#7d8eb0';
    ctx.beginPath();
    ctx.moveTo(cx - 18, 238);
    ctx.lineTo(cx, 250);
    ctx.lineTo(cx + 18, 238);
    ctx.closePath();
    ctx.fill();

    // ── Neck ──
    ctx.fillStyle = skinShadow;
    ctx.beginPath();
    ctx.roundRect(cx - 14, 216, 28, 28, 6);
    ctx.fill();

    // ── Head (large, cute proportions) ──
    // Shadow under head
    ctx.fillStyle = '#00000008';
    ctx.beginPath();
    ctx.ellipse(cx, 220, 55, 12, 0, 0, Math.PI * 2);
    ctx.fill();

    // Main head shape
    const headGrad = ctx.createRadialGradient(cx - 15, 130, 10, cx, 150, 80);
    headGrad.addColorStop(0, skin);
    headGrad.addColorStop(1, skinShadow);
    ctx.fillStyle = headGrad;
    ctx.beginPath();
    ctx.ellipse(cx, 145, 68, 78, 0, 0, Math.PI * 2);
    ctx.fill();

    // ── Ears ──
    for (const ex of [-65, 65]) {
      ctx.fillStyle = skinShadow;
      ctx.beginPath();
      ctx.ellipse(cx + ex, 150, 10, 16, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = skin;
      ctx.beginPath();
      ctx.ellipse(cx + ex, 150, 7, 12, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Hair ──
    const hairGrad = ctx.createLinearGradient(cx, 55, cx, 110);
    hairGrad.addColorStop(0, hair);
    hairGrad.addColorStop(1, hair + 'dd');
    ctx.fillStyle = hairGrad;
    ctx.beginPath();
    ctx.ellipse(cx, 95, 72, 55, 0, 0, Math.PI * 2);
    ctx.fill();
    // Front fringe
    ctx.beginPath();
    ctx.ellipse(cx - 20, 85, 40, 22, -0.15, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(cx + 15, 82, 35, 20, 0.1, 0, Math.PI * 2);
    ctx.fill();
    // Hair shine
    ctx.fillStyle = '#ffffff10';
    ctx.beginPath();
    ctx.ellipse(cx - 15, 72, 25, 12, -0.3, 0, Math.PI * 2);
    ctx.fill();

    // ── Eyes (big, cute anime-style) ──
    const eyeY = 148 - s.surprise * 3;
    for (const side of [-1, 1]) {
      const ex = cx + side * 26;

      // Eye socket shadow
      ctx.fillStyle = '#00000008';
      ctx.beginPath();
      ctx.ellipse(ex, eyeY + 2, 18, 16, 0, 0, Math.PI * 2);
      ctx.fill();

      // Eye white
      const eyeH = 15 * (1 + s.surprise * 0.2);
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.ellipse(ex, eyeY, 16, eyeH, 0, 0, Math.PI * 2);
      ctx.fill();
      // Eye outline
      ctx.strokeStyle = '#c8b8a8';
      ctx.lineWidth = 0.8;
      ctx.stroke();

      if (eyeClose < 0.8) {
        // Iris
        const irisGrad = ctx.createRadialGradient(ex + s.pupilX, eyeY + s.pupilY - 1, 2, ex + s.pupilX, eyeY + s.pupilY, 10);
        irisGrad.addColorStop(0, '#6b4423');
        irisGrad.addColorStop(0.7, '#4a2e15');
        irisGrad.addColorStop(1, '#3a2010');
        ctx.fillStyle = irisGrad;
        ctx.beginPath();
        ctx.ellipse(ex + s.pupilX, eyeY + s.pupilY, 9, 10, 0, 0, Math.PI * 2);
        ctx.fill();

        // Pupil
        ctx.fillStyle = '#0a0a0a';
        ctx.beginPath();
        ctx.ellipse(ex + s.pupilX, eyeY + s.pupilY, 5, 5.5, 0, 0, Math.PI * 2);
        ctx.fill();

        // Eye highlights (two for that anime sparkle)
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(ex + s.pupilX + 3, eyeY + s.pupilY - 4, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(ex + s.pupilX - 2, eyeY + s.pupilY + 2, 1.5, 0, Math.PI * 2);
        ctx.fill();
      }

      // Eyelid (blink)
      if (eyeClose > 0.05) {
        ctx.fillStyle = skin;
        ctx.beginPath();
        ctx.ellipse(ex, eyeY - eyeH + eyeClose * eyeH * 1.8, 17, eyeClose * eyeH * 1.1, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // Upper eyelid line (always visible — adds expression)
      ctx.strokeStyle = '#8b7b6b';
      ctx.lineWidth = 1.8;
      ctx.beginPath();
      const lidCurve = -3 - s.smile * 2 + s.frown * 1;
      ctx.moveTo(ex - 15, eyeY - 12);
      ctx.quadraticCurveTo(ex, eyeY - 15 + lidCurve, ex + 15, eyeY - 12);
      ctx.stroke();
    }

    // ── Eyebrows ──
    for (const side of [-1, 1]) {
      const bx = cx + side * 26;
      const by = 124 - s.browRaise * 6 + s.browFurrow * 2;

      ctx.strokeStyle = hair;
      ctx.lineWidth = 3;
      ctx.lineCap = 'round';
      ctx.beginPath();

      const tilt = (s.browRaise * 4 - s.browFurrow * 3) * side;
      ctx.moveTo(bx - side * 14, by + tilt);
      ctx.quadraticCurveTo(bx, by - 3 - s.browRaise * 2, bx + side * 14, by - tilt);
      ctx.stroke();
    }

    // ── Nose ──
    ctx.strokeStyle = skinShadow;
    ctx.lineWidth = 1.5;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(cx - 1, 163);
    ctx.quadraticCurveTo(cx - 4, 172, cx - 2, 175);
    ctx.quadraticCurveTo(cx, 177, cx + 2, 175);
    ctx.stroke();

    // ── Cheeks (blush on happy) ──
    if (s.smile > 0.1) {
      ctx.fillStyle = `rgba(235, 130, 130, ${s.smile * 0.18})`;
      ctx.beginPath();
      ctx.ellipse(cx - 40, 170, 14, 10, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.ellipse(cx + 40, 170, 14, 10, 0, 0, Math.PI * 2);
      ctx.fill();
    }

    // ── Mouth ──
    const my = 188;
    if (s.mouthOpen > 0.15) {
      // Speaking — open mouth
      const openH = 4 + s.mouthOpen * 10;
      const openW = 10 + s.mouthOpen * 4;
      // Mouth shape
      ctx.fillStyle = '#c0392b';
      ctx.beginPath();
      ctx.ellipse(cx, my + openH * 0.3, openW, openH, 0, 0, Math.PI * 2);
      ctx.fill();
      // Tongue hint
      ctx.fillStyle = '#e07065';
      ctx.beginPath();
      ctx.ellipse(cx, my + openH * 0.6, openW * 0.6, openH * 0.4, 0, 0, Math.PI);
      ctx.fill();
      // Teeth
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.ellipse(cx, my - openH * 0.15, openW * 0.7, openH * 0.25, 0, 0, Math.PI, true);
      ctx.fill();
    } else {
      // Resting expression mouth
      ctx.strokeStyle = '#8b5e3c';
      ctx.lineWidth = 2.2;
      ctx.lineCap = 'round';
      ctx.beginPath();
      const smileCurve = 6 * s.smile - 5 * s.frown;
      ctx.moveTo(cx - 14, my);
      ctx.quadraticCurveTo(cx, my + smileCurve, cx + 14, my);
      ctx.stroke();

      // Smile dimples
      if (s.smile > 0.3) {
        ctx.strokeStyle = `rgba(139, 94, 60, ${s.smile * 0.4})`;
        ctx.lineWidth = 1.2;
        for (const side of [-1, 1]) {
          ctx.beginPath();
          ctx.arc(cx + side * 18, my + 1, 4, side > 0 ? 0 : Math.PI, side > 0 ? Math.PI * 0.6 : Math.PI * 1.6);
          ctx.stroke();
        }
      }
    }

    // ── Thinking dots (evaluation state) ──
    if (salesState === 'evaluation' && !isTyping && !isSpeaking) {
      const dotPhase = timestamp * 0.003;
      for (let i = 0; i < 3; i++) {
        const dotAlpha = 0.25 + 0.25 * Math.sin(dotPhase + i * 0.8);
        ctx.fillStyle = `rgba(148, 163, 184, ${dotAlpha})`;
        ctx.beginPath();
        ctx.arc(cx + 75 + i * 12, 90 - i * 12, 5 - i, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    ctx.restore(); // head rotation
    ctx.restore(); // breathing

    // ── Listening bars ──
    if (isListening) {
      const barX = cx - 16;
      for (let i = 0; i < 5; i++) {
        const barH = 6 + Math.abs(Math.sin(timestamp * 0.006 + i * 1.2)) * 12;
        ctx.fillStyle = '#34d399';
        ctx.beginPath();
        ctx.roundRect(barX + i * 8, 290 - barH, 4, barH, 2);
        ctx.fill();
      }
    }

    animRef.current = requestAnimationFrame(draw);
  }, [expression, skin, skinShadow, hair, shirtColor, riskColor, salesState, isTyping, isSpeaking, isListening]);

  // Start/stop animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // Set canvas resolution for retina
    const dpr = window.devicePixelRatio || 1;
    canvas.width = 280 * dpr;
    canvas.height = 320 * dpr;
    canvas.style.width = '280px';
    canvas.style.height = '320px';
    canvas.getContext('2d').scale(dpr, dpr);

    animRef.current = requestAnimationFrame(draw);
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [draw]);

  // Expression hint (memoised to avoid recalc every frame)
  const hint = useMemo(() => {
    const emotionHint = EMOTION_HINTS[expression] || EMOTION_HINTS.neutral;
    const stateTip = STATE_TIPS[salesState] || STATE_TIPS.interest;
    return { ...emotionHint, tip: stateTip };
  }, [expression, salesState]);

  return (
    <div className="relative flex flex-col items-center">
      <canvas
        ref={canvasRef}
        style={{ width: 280, height: 320 }}
      />

      {/* Expression hint card */}
      <div className="w-64 mt-1 transition-all duration-500 ease-out">
        {/* Emotion badge + state label */}
        <div className="flex items-center justify-between px-1 mb-1">
          <div className="flex items-center space-x-1.5">
            <span className="text-sm">{hint.icon}</span>
            <span className="text-[11px] font-bold" style={{ color: hint.color }}>
              {hint.label}
            </span>
          </div>
          <span className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">
            {salesState?.replace('_', ' ')}
          </span>
        </div>

        {/* What the expression means */}
        <div className="px-2.5 py-1.5 bg-white/60 backdrop-blur-sm rounded-lg border border-slate-100">
          <p className="text-[10px] text-slate-500 leading-snug">
            {hint.desc}
          </p>
          <p className="text-[10px] font-medium text-indigo-600 mt-0.5 leading-snug">
            {hint.tip}
          </p>
        </div>
      </div>
    </div>
  );
}
