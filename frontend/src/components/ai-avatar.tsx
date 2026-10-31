/**
 * AI Avatar — realistic human portrait for a natural video-call experience.
 *
 * A semi-realistic illustrated woman with:
 * - Warm, natural skin tones with gradient shading
 * - Dark brown wavy hair with highlights
 * - Detailed hazel-brown eyes that track the user via webcam
 * - Realistic mouth shapes that animate during speech (visemes)
 * - Natural blinking (random intervals, occasional double-blink)
 * - Subtle breathing animation (CSS-driven, no JS re-renders)
 * - Micro-expressions: brow raises, cheek flush, head tilts
 * - Professional appearance: shoulders, clothing, neck
 *
 * Feels like talking to a real person in a video call.
 * Pure SVG + CSS animations — zero external dependencies.
 */

"use client";

import { useEffect, useState } from "react";
import type { FaceTrackingData } from "@/hooks/use-face-tracking";

type AvatarState = "idle" | "listening" | "thinking" | "speaking";

interface AIAvatarProps {
  state: AvatarState;
  amplitude?: number;
  faceTracking?: FaceTrackingData | null;
  className?: string;
}

/* ─── Mouth viseme shapes (centred at x=150, y≈237) ──────────── */
const VISEMES: Record<string, string> = {
  rest: "M 133,237 Q 150,243 167,237",
  smile: "M 131,236 Q 150,247 169,236",
  ah: "M 131,234 Q 150,254 169,234 Q 150,248 131,234",
  oh: "M 137,234 Q 150,250 163,234 Q 150,245 137,234",
  ee: "M 128,236 Q 150,243 172,236",
  mm: "M 134,237 Q 150,240 166,237",
};

const SPEAK_SEQ: (keyof typeof VISEMES)[] = [
  "ah", "ee", "oh", "mm", "ah", "rest", "oh", "ee", "mm", "rest",
];

export function AIAvatar({
  state,
  amplitude = 0,
  faceTracking = null,
  className = "",
}: AIAvatarProps) {
  /* ── state ────────────────────────────────────────────────── */
  const [blink, setBlink] = useState(false);
  const [mouthIdx, setMouthIdx] = useState(0);
  const [microMove, setMicroMove] = useState({ x: 0, y: 0 });
  const [nodPhase, setNodPhase] = useState(0);

  /* ── Natural blink (2.5-5.5 s, occasional double-blink) ──── */
  useEffect(() => {
    let tid: ReturnType<typeof setTimeout>;
    const schedule = () => {
      tid = setTimeout(() => {
        setBlink(true);
        const double = Math.random() < 0.15;
        setTimeout(() => {
          setBlink(false);
          if (double) {
            setTimeout(() => {
              setBlink(true);
              setTimeout(() => setBlink(false), 110);
            }, 170);
          }
        }, 130);
        schedule();
      }, 2500 + Math.random() * 3000);
    };
    schedule();
    return () => clearTimeout(tid);
  }, []);

  /* ── Mouth cycle when speaking ──────────────────────────── */
  useEffect(() => {
    if (state !== "speaking") { setMouthIdx(0); return; }
    const id = setInterval(
      () => setMouthIdx((i) => (i + 1) % SPEAK_SEQ.length),
      130,
    );
    return () => clearInterval(id);
  }, [state]);

  /* ── Micro saccades (subtle random eye drift) ──────────── */
  useEffect(() => {
    const id = setInterval(() => {
      if (Math.random() < 0.3) {
        setMicroMove({
          x: (Math.random() - 0.5) * 2,
          y: (Math.random() - 0.5) * 1.5,
        });
      }
    }, 2200);
    return () => clearInterval(id);
  }, []);

  /* ── Listening nod ──────────────────────────────────────── */
  useEffect(() => {
    if (state !== "listening" || !faceTracking?.isTalking) {
      setNodPhase(0);
      return;
    }
    const id = setInterval(() => setNodPhase((p) => (p === 0 ? 2.5 : 0)), 800);
    return () => clearInterval(id);
  }, [state, faceTracking?.isTalking]);

  /* ── derived values ─────────────────────────────────────── */
  const gazeX = faceTracking?.faceDetected
    ? faceTracking.faceX * 4 + microMove.x
    : state === "thinking" ? 3 + microMove.x
    : microMove.x;

  const gazeY = faceTracking?.faceDetected
    ? faceTracking.faceY * 3 + microMove.y
    : state === "thinking" ? -3 + microMove.y
    : microMove.y;

  const eyeOpen = blink ? 0.05 : state === "listening" ? 1.12 : 1.0;

  const headRot = (() => {
    if (state === "listening") {
      const base = faceTracking?.faceDetected ? faceTracking.faceX * -4 : -3;
      return base + nodPhase;
    }
    if (state === "thinking") return 4;
    return 0; // idle & speaking: CSS handles speaking wobble
  })();

  const browY = (() => {
    if (state === "listening" && faceTracking?.isTalking) return -3;
    if (state === "listening") return -1.5;
    if (state === "thinking") return 1.5;
    return 0;
  })();

  const mouthPath = (() => {
    if (state === "speaking") return VISEMES[SPEAK_SEQ[mouthIdx]];
    if (state === "thinking") return VISEMES.mm;
    if (state === "listening" && faceTracking?.isTalking) return VISEMES.oh;
    return VISEMES.smile;
  })();

  const mouthFill =
    state === "speaking" && ["ah", "oh"].includes(SPEAK_SEQ[mouthIdx])
      ? "#4A1E1E" : "none";

  const cheekFlush =
    state === "speaking" ? 0.14
    : state === "listening" ? 0.1
    : 0.06;

  const statusColor =
    state === "speaking" ? "#6366f1"
    : state === "thinking" ? "#f59e0b"
    : state === "listening" ? "#22c55e"
    : "transparent";

  /* ── eyelid helpers ─────────────────────────────────────── */
  const lidClose = 1 - eyeOpen;
  const ulY1 = 167 + lidClose * 11;   // upper-lid control-point Y
  const ulY2 = 166 + lidClose * 12;   // upper-lid center Y
  const lashVis = eyeOpen > 0.5;

  /* ─────────────────────────────────────────────────────────── */
  return (
    <div className={`relative flex items-center justify-center ${className}`}>
      {/* Ambient warm glow */}
      <div
        className="absolute rounded-full blur-3xl transition-all duration-1000 pointer-events-none"
        style={{
          inset: "15%",
          background: state === "speaking"
            ? "radial-gradient(ellipse at 50% 40%, rgba(99,102,241,0.12) 0%, transparent 70%)"
            : state === "thinking"
            ? "radial-gradient(ellipse at 50% 40%, rgba(245,158,11,0.07) 0%, transparent 70%)"
            : "radial-gradient(ellipse at 50% 40%, rgba(255,220,180,0.05) 0%, transparent 70%)",
        }}
      />

      <svg
        viewBox="0 0 300 380"
        className="relative w-full h-full"
        style={{
          maxWidth: "min(92%, 400px)",
          maxHeight: "min(94%, 460px)",
          filter: "drop-shadow(0 8px 30px rgba(0,0,0,0.35))",
        }}
      >
        {/* ═══ DEFS ═══ */}
        <defs>
          {/* Skin */}
          <linearGradient id="skinBase" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#F2D0B8" />
            <stop offset="50%" stopColor="#E8C0A4" />
            <stop offset="100%" stopColor="#DAA090" />
          </linearGradient>
          <linearGradient id="skinNeck" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#D4A88E" />
            <stop offset="100%" stopColor="#C89878" />
          </linearGradient>

          {/* Hair */}
          <linearGradient id="hairMain" x1="0.2" y1="0" x2="0.8" y2="1">
            <stop offset="0%" stopColor="#1C110A" />
            <stop offset="40%" stopColor="#2A1810" />
            <stop offset="100%" stopColor="#3D2518" />
          </linearGradient>
          <linearGradient id="hairHL" x1="0.3" y1="0" x2="0.7" y2="1">
            <stop offset="0%" stopColor="#4A3020" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#3D2518" stopOpacity="0" />
          </linearGradient>

          {/* Eyes */}
          <radialGradient id="irisG" cx="0.45" cy="0.4" r="0.5">
            <stop offset="0%" stopColor="#8B6A40" />
            <stop offset="45%" stopColor="#6B4A28" />
            <stop offset="100%" stopColor="#3D2815" />
          </radialGradient>

          {/* Lips */}
          <linearGradient id="lipG" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#C87068" />
            <stop offset="100%" stopColor="#B86060" />
          </linearGradient>

          {/* Clothing */}
          <linearGradient id="clothG" x1="0.5" y1="0" x2="0.5" y2="1">
            <stop offset="0%" stopColor="#2D3748" />
            <stop offset="100%" stopColor="#1A202C" />
          </linearGradient>
        </defs>

        {/* ═══ BREATHING WRAPPER (CSS animation) ═══ */}
        <g className="animate-human-breathe">

          {/* ── Hair behind head ── */}
          <path
            d="M 80,110 C 68,68 95,42 150,38 C 205,42 232,68 220,110
               L 228,185 Q 235,235 226,275 Q 220,305 208,325 L 200,335
               Q 178,340 165,330 L 155,308 L 150,300 L 145,308 L 135,330
               Q 122,340 100,335 L 92,325 Q 80,305 74,275 Q 65,235 72,185 Z"
            fill="url(#hairMain)"
          />
          {/* Hair volume highlight */}
          <path
            d="M 90,105 C 85,72 108,50 150,46 C 192,50 215,72 210,105
               L 215,165 Q 212,195 208,215"
            fill="url(#hairHL)" opacity="0.35"
          />

          {/* ── Shoulders + Clothing ── */}
          <path
            d="M 55,380 L 55,318 Q 60,293 82,283 Q 108,273 132,270
               L 150,268 L 168,270 Q 192,273 218,283 Q 240,293 245,318
               L 245,380 Z"
            fill="url(#clothG)"
          />
          {/* V-neckline */}
          <path d="M 122,274 Q 137,294 150,298 Q 163,294 178,274"
            fill="none" stroke="#1A202C" strokeWidth="1.5" opacity="0.45" />
          {/* Collar shadow */}
          <path d="M 118,276 Q 134,298 150,302 Q 166,298 182,276"
            fill="none" stroke="#334155" strokeWidth="1" opacity="0.2" />

          {/* ── Neck ── */}
          <path
            d="M 133,260 Q 131,266 132,274 L 132,280
               Q 141,286 150,287 Q 159,286 168,280
               L 168,274 Q 169,266 167,260"
            fill="url(#skinNeck)"
          />
          <ellipse cx="150" cy="267" rx="20" ry="5" fill="#B8886E" opacity="0.15" />

          {/* ═══ HEAD (speaking wobble via CSS + dynamic tilt) ═══ */}
          <g
            className={state === "speaking" ? "animate-speak-head" : ""}
            style={{ transformOrigin: "150px 190px" }}
          >
            <g
              style={{
                transform: `rotate(${headRot}deg)`,
                transformOrigin: "150px 190px",
                transition: "transform 0.5s cubic-bezier(0.25,0.46,0.45,0.94)",
              }}
            >
              {/* ── Face shape (realistic jawline) ── */}
              <path
                d="M 150,96
                   C 202,96 228,128 229,172
                   C 230,208 220,238 200,253
                   Q 178,270 150,274
                   Q 122,270 100,253
                   C 80,238 70,208 71,172
                   C 72,128 98,96 150,96 Z"
                fill="#E8C0A4"
              />

              {/* Face subtle side shadow */}
              <path
                d="M 229,172 C 230,208 220,238 200,253
                   Q 178,270 150,274 L 150,96
                   C 202,96 228,128 229,172 Z"
                fill="#DDAA90" opacity="0.12"
              />

              {/* Forehead highlight */}
              <ellipse cx="147" cy="130" rx="34" ry="24" fill="#F5DCC8" opacity="0.25" />

              {/* ── Ears ── */}
              <ellipse cx="72" cy="182" rx="9" ry="15" fill="#E0B498" />
              <ellipse cx="74" cy="182" rx="5.5" ry="10" fill="#D4A88E" opacity="0.45" />
              <ellipse cx="228" cy="182" rx="9" ry="15" fill="#E0B498" />
              <ellipse cx="226" cy="182" rx="5.5" ry="10" fill="#D4A88E" opacity="0.45" />

              {/* ── Eyebrows ── */}
              <path
                d={state === "thinking"
                  ? "M 106,161 Q 117,156 130,159"
                  : state === "listening"
                  ? "M 107,159 Q 117,153 130,157"
                  : "M 107,162 Q 117,157 130,160"}
                fill="none" stroke="#3D2518" strokeWidth="2.5" strokeLinecap="round"
                style={{
                  transform: `translateY(${browY}px)`,
                  transition: "all 0.35s ease-out",
                }}
              />
              <path
                d={state === "thinking"
                  ? "M 170,159 Q 183,156 194,161"
                  : state === "listening"
                  ? "M 170,157 Q 183,153 193,159"
                  : "M 170,160 Q 183,157 193,162"}
                fill="none" stroke="#3D2518" strokeWidth="2.5" strokeLinecap="round"
                style={{
                  transform: `translateY(${browY}px)`,
                  transition: "all 0.35s ease-out",
                }}
              />

              {/* ══ LEFT EYE ══ */}
              <g style={{
                transform: `translate(${gazeX * 0.3}px, ${gazeY * 0.2}px)`,
                transition: "transform 0.35s ease-out",
              }}>
                {/* Sclera */}
                <ellipse cx="122" cy="178" rx="16" ry={12 * eyeOpen}
                  fill="white" className="transition-all duration-100" />
                {/* Upper lid shadow */}
                <ellipse cx="122" cy="172" rx="15" ry="3.5"
                  fill="#D4A88E" opacity={lashVis ? 0.12 : 0} />
                {/* Iris */}
                <circle cx={122 + gazeX * 0.6} cy={178 + gazeY * 0.4}
                  r={8 * Math.min(1, eyeOpen)} fill="url(#irisG)"
                  className="transition-all duration-150" />
                {/* Pupil */}
                <circle cx={122 + gazeX * 0.7} cy={178 + gazeY * 0.45}
                  r={3.5 * Math.min(1, eyeOpen)} fill="#0A0604"
                  className="transition-all duration-150" />
                {/* Catchlights */}
                <circle cx={126 + gazeX * 0.3} cy={174 + gazeY * 0.15}
                  r="2.2" fill="white" opacity={lashVis ? 0.92 : 0} />
                <circle cx={119 + gazeX * 0.25} cy={181}
                  r="1.2" fill="white" opacity={lashVis ? 0.3 : 0} />
                {/* Upper lash line */}
                <path
                  d={`M 106,178 Q 114,${ulY1} 122,${ulY2} Q 130,${ulY1} 138,178`}
                  fill="none" stroke="#1C110A" strokeWidth="2.2" strokeLinecap="round"
                  className="transition-all duration-100"
                />
                {/* Outer lash wing */}
                <path
                  d={`M 136,${176 + lidClose * 2} L 140,${173 + lidClose * 5}`}
                  fill="none" stroke="#1C110A" strokeWidth="1.5" strokeLinecap="round"
                  className="transition-all duration-100"
                />
                {/* Lower lid */}
                <path d="M 108,180 Q 122,188 136,180"
                  fill="none" stroke="#C8967E" strokeWidth="0.7" opacity="0.35" />
              </g>

              {/* ══ RIGHT EYE ══ */}
              <g style={{
                transform: `translate(${gazeX * 0.3}px, ${gazeY * 0.2}px)`,
                transition: "transform 0.35s ease-out",
              }}>
                <ellipse cx="178" cy="178" rx="16" ry={12 * eyeOpen}
                  fill="white" className="transition-all duration-100" />
                <ellipse cx="178" cy="172" rx="15" ry="3.5"
                  fill="#D4A88E" opacity={lashVis ? 0.12 : 0} />
                <circle cx={178 + gazeX * 0.6} cy={178 + gazeY * 0.4}
                  r={8 * Math.min(1, eyeOpen)} fill="url(#irisG)"
                  className="transition-all duration-150" />
                <circle cx={178 + gazeX * 0.7} cy={178 + gazeY * 0.45}
                  r={3.5 * Math.min(1, eyeOpen)} fill="#0A0604"
                  className="transition-all duration-150" />
                <circle cx={182 + gazeX * 0.3} cy={174 + gazeY * 0.15}
                  r="2.2" fill="white" opacity={lashVis ? 0.92 : 0} />
                <circle cx={175 + gazeX * 0.25} cy={181}
                  r="1.2" fill="white" opacity={lashVis ? 0.3 : 0} />
                <path
                  d={`M 162,178 Q 170,${ulY1} 178,${ulY2} Q 186,${ulY1} 194,178`}
                  fill="none" stroke="#1C110A" strokeWidth="2.2" strokeLinecap="round"
                  className="transition-all duration-100"
                />
                <path
                  d={`M 192,${176 + lidClose * 2} L 196,${173 + lidClose * 5}`}
                  fill="none" stroke="#1C110A" strokeWidth="1.5" strokeLinecap="round"
                  className="transition-all duration-100"
                />
                <path d="M 164,180 Q 178,188 192,180"
                  fill="none" stroke="#C8967E" strokeWidth="0.7" opacity="0.35" />
              </g>

              {/* ── Nose ── */}
              <line x1="150" y1="178" x2="150" y2="210"
                stroke="#F2D0B8" strokeWidth="3.5" strokeLinecap="round" opacity="0.25" />
              <ellipse cx="150" cy="214" rx="7.5" ry="4.5" fill="#DDAA90" opacity="0.2" />
              <circle cx="143" cy="216" r="2.8" fill="#C8907A" opacity="0.18" />
              <circle cx="157" cy="216" r="2.8" fill="#C8907A" opacity="0.18" />
              <path d="M 141,220 Q 150,224 159,220"
                fill="none" stroke="#C8907A" strokeWidth="0.7" opacity="0.15" />

              {/* ── Mouth / Lips ── */}
              {/* Mouth interior (when open) */}
              {mouthFill !== "none" && (
                <path d={mouthPath} fill={mouthFill} opacity="0.55"
                  className="transition-all duration-75" />
              )}
              {/* Teeth hint (when wide open) */}
              {state === "speaking" && SPEAK_SEQ[mouthIdx] === "ah" && (
                <rect x="140" y="236" width="20" height="5" rx="2"
                  fill="white" opacity="0.55" />
              )}
              {/* Upper lip */}
              <path
                d={state === "speaking"
                  ? mouthPath
                  : "M 133,237 Q 142,232 150,234 Q 158,232 167,237"}
                fill={state === "speaking" ? "url(#lipG)" : "none"}
                stroke="#C07068" strokeWidth="1.8" strokeLinecap="round"
                className="transition-all duration-100"
              />
              {/* Lower lip */}
              <path
                d={state === "speaking"
                  ? (["ah", "oh"].includes(SPEAK_SEQ[mouthIdx])
                    ? `M 133,238 Q 150,${249 + (SPEAK_SEQ[mouthIdx] === "ah" ? 5 : 2)} 167,238`
                    : "M 134,238 Q 150,245 166,238")
                  : "M 133,238 Q 150,247 167,238"}
                fill="url(#lipG)" opacity="0.55"
                className="transition-all duration-100"
              />
              {/* Lip centre line */}
              <path d={mouthPath}
                fill="none" stroke="#A05050" strokeWidth="0.6" opacity="0.2"
                className="transition-all duration-100" />
              {/* Lower lip highlight */}
              <ellipse cx="150" cy="242" rx="8" ry="2" fill="white" opacity="0.06" />

              {/* ── Cheeks ── */}
              <circle cx="96" cy="210" r="15" fill="#E8A090"
                opacity={cheekFlush} className="transition-opacity duration-500" />
              <circle cx="204" cy="210" r="15" fill="#E8A090"
                opacity={cheekFlush} className="transition-opacity duration-500" />

              {/* ── Chin shadow ── */}
              <ellipse cx="150" cy="265" rx="28" ry="7" fill="#C89078" opacity="0.08" />

              {/* ═══ HAIR FRONT ═══ */}
              {/* Bangs / fringe (left sweep) */}
              <path
                d="M 78,118 C 80,92 100,70 122,66 Q 138,64 148,70
                   L 152,82 Q 150,92 142,102 L 126,116 Q 102,122 88,126 Z"
                fill="url(#hairMain)"
              />
              {/* Side strand left */}
              <path d="M 73,132 Q 70,165 74,195 Q 73,215 78,230"
                fill="none" stroke="#2A1810" strokeWidth="11" strokeLinecap="round" opacity="0.75" />
              {/* Side strand right */}
              <path d="M 227,132 Q 230,165 226,195 Q 227,215 222,230"
                fill="none" stroke="#2A1810" strokeWidth="11" strokeLinecap="round" opacity="0.75" />
              {/* Hair highlight streaks */}
              <path d="M 100,78 Q 118,68 132,70"
                fill="none" stroke="#5A3825" strokeWidth="2" opacity="0.25" />
              <path d="M 85,98 Q 102,86 118,90"
                fill="none" stroke="#5A3825" strokeWidth="1.5" opacity="0.2" />
            </g>
          </g>
          {/* end head */}

        </g>
        {/* end breathing wrapper */}

        {/* ═══ SUBTLE STATE INDICATORS ═══ */}

        {/* Speaking: soft sound ripples near mouth */}
        {state === "speaking" && (
          <>
            <circle cx="150" cy="240" r="5" fill="none"
              stroke={statusColor} strokeWidth="1" opacity="0.25">
              <animate attributeName="r" values="5;28" dur="1.6s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.25;0" dur="1.6s" repeatCount="indefinite" />
            </circle>
            <circle cx="150" cy="240" r="5" fill="none"
              stroke={statusColor} strokeWidth="0.8" opacity="0.15">
              <animate attributeName="r" values="5;28" dur="1.6s" begin="0.5s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.15;0" dur="1.6s" begin="0.5s" repeatCount="indefinite" />
            </circle>
          </>
        )}

        {/* Thinking: warm glow around head */}
        {state === "thinking" && (
          <circle cx="150" cy="140" r="55" fill={statusColor} opacity="0.035">
            <animate attributeName="opacity" values="0.035;0.07;0.035" dur="2.5s" repeatCount="indefinite" />
          </circle>
        )}

        {/* Listening: subtle arcs near ears */}
        {state === "listening" && (
          <>
            <path d="M 60,178 Q 48,182 60,188" fill="none"
              stroke={statusColor} strokeWidth="1.5" opacity="0.25">
              <animate attributeName="opacity" values="0.25;0.08;0.25" dur="1.3s" repeatCount="indefinite" />
            </path>
            <path d="M 52,173 Q 38,182 52,193" fill="none"
              stroke={statusColor} strokeWidth="1" opacity="0.12">
              <animate attributeName="opacity" values="0.12;0.03;0.12" dur="1.3s" begin="0.3s" repeatCount="indefinite" />
            </path>
            <path d="M 240,178 Q 252,182 240,188" fill="none"
              stroke={statusColor} strokeWidth="1.5" opacity="0.25">
              <animate attributeName="opacity" values="0.25;0.08;0.25" dur="1.3s" repeatCount="indefinite" />
            </path>
            <path d="M 248,173 Q 262,182 248,193" fill="none"
              stroke={statusColor} strokeWidth="1" opacity="0.12">
              <animate attributeName="opacity" values="0.12;0.03;0.12" dur="1.3s" begin="0.3s" repeatCount="indefinite" />
            </path>
          </>
        )}
      </svg>

      {/* Status label */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2">
        <span
          className={`text-[10px] font-medium px-3 py-1 rounded-full backdrop-blur-sm transition-all duration-300 ${
            state === "speaking"
              ? "bg-indigo-500/20 text-indigo-300"
              : state === "thinking"
              ? "bg-amber-500/15 text-amber-300"
              : state === "listening"
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-white/5 text-white/40"
          }`}
        >
          {state === "speaking"
            ? "Speaking"
            : state === "thinking"
            ? "Thinking..."
            : state === "listening"
            ? "Listening"
            : "Aria"}
        </span>
      </div>
    </div>
  );
}
