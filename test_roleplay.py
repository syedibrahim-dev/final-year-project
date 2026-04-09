"""
╔══════════════════════════════════════════════════════════════╗
║          ROLEPLAY TEST MODULE — CLI Test Runner             ║
║  Bypasses UI/auth, directly calls the orchestrator.         ║
║  Tests multi-turn conversations, shows all agent outputs,   ║
║  and runs post-session evaluation.                          ║
║                                                              ║
║  DUAL PREDICTION:                                            ║
║    • During roleplay: keyword-based model (instant)          ║
║    • Post-session: SalesRLAgent / deepmost (LLM-powered)     ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    # Auto mode with RAG documents
    python test_roleplay.py --auto --persona 1 --org-id 1 --verbose

    # Auto mode — runs a predefined sales script automatically
    python test_roleplay.py --auto

    # Pick a specific persona (1-8)
    python test_roleplay.py --auto --persona 3

    # Skip deepmost comparison (faster)
    python test_roleplay.py --auto --no-deepmost

    # Show all agent outputs verbosely
    python test_roleplay.py --auto --verbose
"""

import sys
import json
import argparse
import subprocess
import tempfile
import os
from pathlib import Path
from types import SimpleNamespace

# ── Make imports work from project root ──
sys.path.insert(0, str(Path(__file__).parent))

from roleplay.orchestrator import AgentOrchestrator

# ── Deepmost SalesRLAgent config ──
DEEPMOST_PYTHON = r"D:\fyp-2026\venv311_deepmost\Scripts\python.exe"
DEEPMOST_SCRIPT = str(Path(__file__).parent / "conversion" / "deepmost_predictor.py")


# ══════════════════════════════════════════════════════════════
#  PERSONA DEFINITIONS (mirror of data/personas.json)
# ══════════════════════════════════════════════════════════════

PERSONAS = [
    SimpleNamespace(
        id=1, name="The Friendly Prospect", difficulty="beginner", tone="casual",
        description="Enthusiastic but indecisive department manager.",
        scenario_brief="Speaking with a sales rep your colleague recommended.",
        personality_traits={"patience": "high", "price_sensitivity": "medium",
                            "decision_speed": "medium", "trust_level": "high",
                            "tech_savviness": "medium", "rag_probing_style": "curious"},
        trigger_topics={"team_buy_in": "When team buy-in is mentioned, you light up."},
        common_objections=["I'd want to loop my team in first.",
                           "I'm not sure this is the right moment for us."],
    ),
    SimpleNamespace(
        id=2, name="The Budget Hunter", difficulty="beginner", tone="casual",
        description="Cost-conscious ops manager, always asks about price.",
        scenario_brief="Agreed to this call because someone forwarded a flyer.",
        personality_traits={"patience": "medium", "price_sensitivity": "very_high",
                            "decision_speed": "slow", "trust_level": "medium",
                            "tech_savviness": "low", "rag_probing_style": "challenge"},
        trigger_topics={"pricing": "Immediately asks about hidden fees."},
        common_objections=["Your competitor is offering something similar for less.",
                           "Can we talk about a discount?"],
    ),
    SimpleNamespace(
        id=3, name="The Busy Executive", difficulty="intermediate", tone="formal",
        description="Senior VP, zero tolerance for vagueness, decides fast.",
        scenario_brief="Has exactly 10 minutes between meetings.",
        personality_traits={"patience": "very_low", "price_sensitivity": "low",
                            "decision_speed": "fast", "trust_level": "medium",
                            "tech_savviness": "medium", "rag_probing_style": "challenge"},
        trigger_topics={"long_explanations": "Cuts you off if too wordy."},
        common_objections=["Tell me in one sentence why this is worth my time.",
                           "Just tell me the number."],
    ),
    SimpleNamespace(
        id=4, name="The Detail Seeker", difficulty="intermediate", tone="formal",
        description="Methodical IT manager, asks deep follow-up questions.",
        scenario_brief="Evaluating this solution for your director.",
        personality_traits={"patience": "high", "price_sensitivity": "medium",
                            "decision_speed": "slow", "trust_level": "high",
                            "tech_savviness": "high", "rag_probing_style": "curious"},
        trigger_topics={"integrations": "Asks about specific API specs and data sync."},
        common_objections=["I need to understand exactly how it integrates.",
                           "Can you send the technical documentation?"],
    ),
    SimpleNamespace(
        id=5, name="The Skeptic", difficulty="advanced", tone="formal",
        description="Evidence-based procurement professional, trusts nothing without proof.",
        scenario_brief="Already researched your company and came with hard questions.",
        personality_traits={"patience": "low", "price_sensitivity": "medium",
                            "decision_speed": "very_slow", "trust_level": "very_low",
                            "tech_savviness": "high", "rag_probing_style": "gotcha"},
        trigger_topics={"bold_claims": "Challenges any 'best' or 'guaranteed' claims."},
        common_objections=["What actual evidence do you have?",
                           "Can you provide independent references I can call?"],
    ),
    SimpleNamespace(
        id=6, name="The Gatekeeper", difficulty="intermediate", tone="formal",
        description="Exec assistant screening vendors, cannot commit to anything.",
        scenario_brief="Your director asked you to take this call and filter.",
        personality_traits={"patience": "medium", "price_sensitivity": "low",
                            "decision_speed": "very_slow", "trust_level": "medium",
                            "tech_savviness": "low", "rag_probing_style": "curious"},
        trigger_topics={"decision_maker": "Won't connect you to the boss easily."},
        common_objections=["I'm not the right person to make this call.",
                           "Can you send me something in writing?"],
    ),
    SimpleNamespace(
        id=7, name="The Competitor Loyalist", difficulty="advanced", tone="casual",
        description="Happy with current vendor, not looking to switch.",
        scenario_brief="Been with current vendor for 3 years, giving you 15 minutes.",
        personality_traits={"patience": "medium", "price_sensitivity": "medium",
                            "decision_speed": "very_slow", "trust_level": "low",
                            "tech_savviness": "medium", "rag_probing_style": "gotcha"},
        trigger_topics={"switching_cost": "Asks why switching is worth the pain."},
        common_objections=["What we have now works.",
                           "Walk me through a side-by-side comparison."],
    ),
    SimpleNamespace(
        id=8, name="The Overwhelmed Owner", difficulty="beginner", tone="casual",
        description="Small business owner, not technical, wants simplicity.",
        scenario_brief="Saw an ad, has 20 minutes, open but easily overwhelmed.",
        personality_traits={"patience": "high", "price_sensitivity": "high",
                            "decision_speed": "medium", "trust_level": "high",
                            "tech_savviness": "low", "rag_probing_style": "curious"},
        trigger_topics={"complexity": "Gets lost with jargon, asks for plain English."},
        common_objections=["I've spent money on software that ended up sitting there.",
                           "How long before this is actually useful?"],
    ),
]


# ══════════════════════════════════════════════════════════════
#  AUTO-PLAY SALES SCRIPTS (trainee messages)
# ══════════════════════════════════════════════════════════════

SALES_SCRIPTS = {
    "beginner": [
        "Hi there! Thanks for taking the time to chat today. I'm really looking forward to learning about your needs.",
        "That's really helpful. Can you tell me a bit more about your current workflow and what challenges you're facing day to day?",
        "I completely understand. We've actually helped teams in similar situations. Our platform reduces onboarding time by 40% and most teams see results within the first two weeks.",
        "Great question. Our pricing starts at $49/month per user, and that includes all features — no hidden fees. We also offer a 30-day free trial.",
        "I hear your concern. What if we set up a quick 15-minute demo so you can see exactly how it works? No pressure at all — just to see if it's a fit.",
        "That sounds perfect. I'll send you a calendar link right after this call. Really appreciate your time today — looking forward to showing you the platform!",
    ],
    "intermediate": [
        "Good afternoon. I appreciate you making time for this — I know you're busy, so I'll be direct. We help companies like yours solve [specific challenge]. Can I ask what your biggest operational bottleneck is right now?",
        "That's exactly the kind of problem we specialize in. Our clients in your space typically see a 3x return within the first quarter. The key differentiator is our integration-first approach — we plug into your existing tools without disruption.",
        "Absolutely — security is a core pillar for us. We're SOC 2 Type II certified, data is encrypted at rest and in transit, and each client gets an isolated environment. I can send you our full security whitepaper after this call.",
        "For implementation, the honest answer is 2-4 weeks depending on complexity. I won't sugarcoat it — some integrations take longer, but we assign a dedicated success manager to keep things on track.",
        "I understand you need to loop in your team. What if I send a one-pager with the key points and ROI projections? That way you have everything you need to brief them efficiently.",
        "Perfect. I'll have that over to you by end of day. Shall we pencil in a 30-minute follow-up next week with your technical lead? That way we can address any deeper questions together.",
    ],
    "advanced": [
        "I know you're not actively looking to switch, and I respect that. I'm not here to sell you something you don't need. What I'd like to do is share how some teams who felt similarly ended up finding significant value. Can I have five minutes to make that case?",
        "Fair point. Your current solution works — I believe that. But let me ask: where does it fall short? Even slightly? Every tool has gaps. Where do you find yourself working around the system rather than with it?",
        "That's a great insight. That specific pain point is actually what drives most of our competitive switches. Our approach is fundamentally different — instead of patching that workflow, we reimagined it. Here's a concrete example with a real client in your industry.",
        "You're right to be skeptical — I'd be the same way. Here's what I can offer: three references from companies who switched from your exact current vendor, a side-by-side comparison on the metrics that matter to you, and a 60-day pilot where you can run both in parallel.",
        "I understand the switching cost concern. That's why we build migration support into our contract — our team handles the data migration, we run parallel systems during transition, and there's a dedicated escalation path. The migration is on us, not on your team's time.",
        "Here's what I'd suggest as a next step: let me send you the case studies from those three clients, plus a detailed migration timeline. Take a week to review. If any of it resonates, I'll arrange a call with one of those reference clients directly. No pressure — just data.",
    ],
}


# ══════════════════════════════════════════════════════════════
#  DISPLAY HELPERS
# ══════════════════════════════════════════════════════════════

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

def hr(char="─", length=60):
    print(f"{DIM}{char * length}{RESET}")

def print_agent_outputs(result, verbose=False):
    """Print all agent outputs for a single turn."""

    # Stage info
    stage = result.get("stage_info")
    if stage:
        st = stage.get("current_stage", "?")
        pct = stage.get("progress_pct", 0)
        print(f"   {DIM}📊 Stage: {st} ({pct}%){RESET}")

    # Coaching hint
    hint = result.get("coaching_hint")
    if hint:
        print(f"   {YELLOW}💡 Coach: {hint}{RESET}")

    # EQ data (transformer-powered: Engine A + Engine B)
    eq = result.get("eq_data")
    if eq:
        score = eq.get("eq_score", 0)
        empathy = eq.get("empathy_score", 0.5)
        pressure = eq.get("pressure_level", "?")
        trend = eq.get("eq_trend", "stable")
        icon = "💚" if empathy >= 0.7 else "🟡" if empathy >= 0.4 else "🔴"
        print(f"   {icon} EQ: {score:.0f}/100 | Empathy: {empathy:.2f} | Pressure: {pressure} | Trend: {trend}")

        if verbose:
            # Engine A: Intent
            if eq.get("is_objection"):
                handling = eq.get("objection_handling", "?")
                obj_conf = eq.get("objection_confidence", 0)
                print(f"      Engine A: Objection detected (conf: {obj_conf:.2f}) → handling: {handling}")
            listening = eq.get("active_listening_score", 0)
            if listening > 0:
                print(f"      Engine A: Active listening: {listening:.2f}")

            # Engine B: Emotion
            prospect_emo = eq.get("prospect_emotion", "?")
            rep_emo = eq.get("rep_dominant_emotion", "?")
            showed = eq.get("rep_showed_empathy", False)
            print(f"      Engine B: Prospect={prospect_emo}, Rep={rep_emo}, Showed empathy={showed}")

    # Accuracy data
    acc = result.get("accuracy_data")
    if acc and acc.get("accuracy_flag") not in ("no_claims", "no_docs", "unavailable", None):
        flag = acc.get("accuracy_flag")
        checked = acc.get("claims_checked", 0)
        flagged = acc.get("flagged_claims", [])
        supported = acc.get("supported_claims", [])
        if flag == "unverified":
            print(f"   {RED}⚠️  Accuracy: {len(flagged)} unverified claim(s) / {checked} checked{RESET}")
            if verbose:
                for c in flagged:
                    print(f"      ✕ \"{c['claim'][:60]}...\" — {c.get('reason', '')}")
        elif flag == "accurate":
            print(f"   {GREEN}✅ Accuracy: {len(supported)}/{checked} claims supported{RESET}")

    # LSTM Conversation Risk (sequence-based trajectory prediction)
    lstm = result.get("lstm_risk")
    if lstm and lstm.get("source") != "unavailable":
        risk = lstm.get("risk_score", 0.5)
        label = lstm.get("risk_label", "?")
        trend = lstm.get("trend", "stable")
        icon = "🟢" if label == "low" else "🟡" if label == "medium" else "🔴"
        trend_arrow = "↗" if trend == "rising" else "↘" if trend == "falling" else "→"
        print(f"   {icon} LSTM Risk: {risk:.1%} [{label}] {trend_arrow} {trend}")

    # Conversion data (SalesRLAgent via deepmost — async, may lag 1 turn)
    conv = result.get("conversion_data")
    if conv and not conv.get("model_not_loaded"):
        prob = conv.get("probability", 0.5)
        trend = conv.get("trend", "neutral")
        status = conv.get("status", "")
        icon = "🟢" if prob >= 0.7 else "🟡" if prob >= 0.45 else "🔴"
        print(f"   {icon} SalesRL: {prob:.1%} [{trend}] {DIM}{status}{RESET}")
        if verbose:
            tp = conv.get("turning_points", [])
            if tp:
                for t in tp:
                    print(f"      ⚡ Turn {t['turn']}: {t['direction']} shift ({t['delta']:+.1%})")


def print_evaluation(eval_data, verbose=False):
    """Print the post-session evaluation report."""
    hr("═")
    print(f"{BOLD}{MAGENTA}  📋 POST-SESSION EVALUATION{RESET}")
    hr("═")

    if not eval_data:
        print(f"  {DIM}(No evaluation data returned){RESET}")
        return

    # Summary
    summary = eval_data.get("summary")
    if summary:
        print(f"\n  {BOLD}Summary:{RESET} {summary}")

    # Category scores
    cats = eval_data.get("llm_category_scores", {})
    if cats:
        print(f"\n  {BOLD}Category Scores:{RESET}")
        total = 0
        for cat, score in cats.items():
            bar = "█" * int(score) + "░" * (20 - int(score))
            label = cat.replace("_", " ").title()
            color = GREEN if score >= 14 else YELLOW if score >= 10 else RED
            print(f"    {label:25s} {color}{bar} {score}/20{RESET}")
            total += score
        print(f"    {'TOTAL':25s} {BOLD}{total}/100{RESET}")

    # Strengths
    strengths = eval_data.get("strengths", [])
    if strengths:
        print(f"\n  {GREEN}{BOLD}✅ Strengths:{RESET}")
        for s in strengths:
            print(f"    ✓ {s}")

    # Improvements
    improvements = eval_data.get("improvements", [])
    if improvements:
        print(f"\n  {YELLOW}{BOLD}📈 Areas to Improve:{RESET}")
        for i, imp in enumerate(improvements, 1):
            print(f"    {i}. {imp}")

    # Coaching tip
    tip = eval_data.get("coaching_tip")
    if tip:
        print(f"\n  {MAGENTA}💡 Key Coaching Tip:{RESET} {tip}")

    # EQ Summary
    eq = eval_data.get("eq_summary", {})
    if eq and eq.get("average_score"):
        print(f"\n  {BOLD}❤️  EQ Summary:{RESET}")
        print(f"    Average: {eq['average_score']:.0f} | Final: {eq.get('final_score', 'N/A')} | Trend: {eq.get('trend', 'N/A')}")

    # Conversion trajectory — DISABLED: handled by SalesRLAgent post-session
    # conv = eval_data.get("conversion_trajectory", {})
    # if conv and conv.get("probabilities"):
    # probs = conv["probabilities"]
    # print(f"\n  {BOLD}📈 Conversion Trajectory:{RESET}")
    # for i, p in enumerate(probs, 1):
    #     bar_len = int(p * 30)
    #     icon = "🟢" if p >= 0.7 else "🟡" if p >= 0.45 else "🔴"
    #     bar = "█" * bar_len + "░" * (30 - bar_len)
    #     print(f"    Turn {i:2d}: {icon} {bar} {p:.1%}")
    # print(f"    Trend: {conv.get('overall_trend', '?')}")

    # Replay annotations
    replay = eval_data.get("replay", {})
    annotations = replay.get("annotations", [])
    if annotations:
        print(f"\n  {BOLD}🔄 Key Moments:{RESET}")
        for a in annotations[:5]:
            type_icon = {"turning_point": "🔄", "strong_moment": "💪",
                         "missed_signal": "👀", "weak_moment": "⚠️"}.get(a.get("type"), "📌")
            print(f"    {type_icon} Msg #{a.get('message_index', '?')} ({a.get('speaker', '?')}): {a.get('comment', '')[:80]}")

    hr("═")


# ══════════════════════════════════════════════════════════════
#  DEEPMOST / SALESRLAGENT POST-SESSION COMPARISON
# ══════════════════════════════════════════════════════════════

def run_deepmost_prediction(messages):
    """
    Run SalesRLAgent (deepmost) as a subprocess on the full transcript.
    Uses venv311_deepmost Python interpreter.
    
    Returns dict with turn-by-turn predictions or None if failed.
    """
    if not Path(DEEPMOST_PYTHON).exists():
        print(f"{RED}  ⚠️  Deepmost Python not found: {DEEPMOST_PYTHON}{RESET}")
        return None
    
    if not Path(DEEPMOST_SCRIPT).exists():
        print(f"{RED}  ⚠️  Deepmost script not found: {DEEPMOST_SCRIPT}{RESET}")
        return None
    
    # Convert messages to JSON format
    transcript = []
    for msg in messages:
        sender = msg.sender if hasattr(msg, 'sender') else msg.get('sender', '')
        text = msg.message_text if hasattr(msg, 'message_text') else msg.get('text', '')
        transcript.append({'sender': sender, 'text': text})
    
    # Write transcript to temp file
    tmp_file = Path(tempfile.gettempdir()) / "roleplay_transcript.json"
    chart_file = Path(tempfile.gettempdir()) / "salesrlagent_trend.png"
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(transcript, f, indent=2)
    
    try:
        print(f"{DIM}  Running SalesRLAgent analysis (Qwen3-4B, may take 1-2 min)...{RESET}")
        result = subprocess.run(
            [DEEPMOST_PYTHON, DEEPMOST_SCRIPT, "--file", str(tmp_file), "--chart", str(chart_file)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max
            cwd=str(Path(__file__).parent),
        )
        
        if result.returncode != 0:
            print(f"{RED}  ⚠️  Deepmost error: {result.stderr[:200]}{RESET}")
            return None
        
        # Parse JSON output (skip any non-JSON lines like warnings)
        stdout = result.stdout.strip()
        # Find the JSON block
        json_start = stdout.find('{')
        if json_start == -1:
            print(f"{RED}  ⚠️  No JSON in deepmost output{RESET}")
            return None
        
        return json.loads(stdout[json_start:])
        
    except subprocess.TimeoutExpired:
        print(f"{RED}  ⚠️  Deepmost timed out (5 min limit){RESET}")
        return None
    except json.JSONDecodeError as e:
        print(f"{RED}  ⚠️  Deepmost JSON parse error: {e}{RESET}")
        return None
    except Exception as e:
        print(f"{RED}  ⚠️  Deepmost error: {e}{RESET}")
        return None
    finally:
        tmp_file.unlink(missing_ok=True)


def print_salesrlagent_analysis(deepmost_result):
    """
    Print SalesRLAgent conversion analysis as the sole conversion prediction.
    Shows: turn-by-turn, turning points, coaching, trend chart.
    """
    hr("═")
    print(f"{BOLD}{CYAN}  📊 SALESRLAGENT — CONVERSION PREDICTION (arXiv:2503.23303){RESET}")
    print(f"  {DIM}Model: RL Policy + Qwen3-4B Dynamic Metrics | Backend: Opensource{RESET}")
    hr("═")

    dm_turns = deepmost_result.get('turn_predictions', [])
    dm_final = deepmost_result.get('final_probability', 0.5)
    dm_status = deepmost_result.get('final_status', '')

    # ── Section 1: Turn-by-Turn Predictions ──
    if dm_turns:
        print(f"\n  {BOLD}Turn-by-Turn Conversion Probability:{RESET}\n")

        for t in dm_turns:
            turn_num = t.get('turn', '?')
            speaker = t.get('speaker', 'unknown')
            prob = t.get('probability', 0.5)
            preview = t.get('message_preview', '')
            metrics = t.get('metrics', {})

            bar_len = int(prob * 30)
            icon = "🟢" if prob >= 0.7 else "🟡" if prob >= 0.45 else "🔴"
            bar = "█" * bar_len + "░" * (30 - bar_len)

            sp_color = GREEN if speaker in ('sales_rep', 'trainee') else CYAN
            sp_label = "🧑‍💼 Sales" if speaker in ('sales_rep', 'trainee') else "👤 Customer"

            print(f"  Turn {turn_num:>2}  {sp_color}{sp_label}{RESET}  {icon} {bar} {prob:.1%}")
            if preview:
                print(f"           {DIM}\"{preview}\"{RESET}")

            if metrics:
                parts = []
                for k, v in list(metrics.items())[:4]:
                    label = k.replace('_', ' ').title()
                    parts.append(f"{label}: {v:.2f}" if isinstance(v, float) else f"{label}: {v}")
                if parts:
                    print(f"           {DIM}Metrics: {' | '.join(parts)}{RESET}")
            print()

        final_icon = "🟢" if dm_final >= 0.7 else "🟡" if dm_final >= 0.45 else "🔴"
        print(f"  {BOLD}Final Conversion Probability: {final_icon} {dm_final:.1%}{RESET}", end="")
        if dm_status:
            print(f"  ({dm_status})", end="")
        print()
    else:
        print(f"\n  {RED}No turn-by-turn data available{RESET}")

    # ── Section 2: Turning Point Analysis ──
    turning_points = deepmost_result.get('turning_points', [])
    significant = deepmost_result.get('significant_turns', [])
    if turning_points:
        print(f"\n  {BOLD}{YELLOW}━━━ TURNING POINT ANALYSIS ━━━{RESET}\n")

        for tp in turning_points:
            change = tp['change']
            if change > 0:
                icon = "📈"
                color = GREEN
            elif change < 0:
                icon = "📉"
                color = RED
            else:
                icon = "➡️"
                color = DIM
            sp_label = "Sales" if tp['speaker'] in ('sales_rep', 'trainee') else "Customer"
            print(f"  Turn {tp['turn']:>2d} ({sp_label:8s}): {color}{icon} {change:+.3f}{RESET}")

        if significant:
            print(f"\n  {BOLD}Biggest Shifts:{RESET}")
            for s in significant[:3]:
                arrow = "↑" if s['direction'] == 'up' else "↓"
                color = GREEN if s['direction'] == 'up' else RED
                print(f"    {color}{arrow} Turn {s['turn']}: {s['change']:+.1%} — \"{s['message_preview'][:50]}...\"{RESET}")

    # ── Section 3: Coaching Suggestions ──
    coaching = deepmost_result.get('coaching_suggestions', [])
    if coaching:
        print(f"\n  {BOLD}{MAGENTA}━━━ COACHING SUGGESTIONS ━━━{RESET}\n")
        for c in coaching:
            icon = c.get('icon', '💡')
            suggestion = c.get('suggestion', c.get('text', str(c)))
            metric_val = c.get('metric_value')
            metric_str = f" (value: {metric_val})" if metric_val is not None else ""
            print(f"  {icon} {suggestion}{DIM}{metric_str}{RESET}")

    # ── Section 4: Trend Visualization ──
    chart_path = deepmost_result.get('chart_path')
    if chart_path:
        print(f"\n  {DIM}📊 Trend chart saved: {chart_path}{RESET}")

    # ── Methodology ──
    print(f"\n  {DIM}Model: SalesRLAgent (arXiv:2503.23303){RESET}")
    print(f"  {DIM}LLM: Qwen3-4B-GGUF (local, opensource) | Trained on 1.2M conversations{RESET}")

    hr("═")


# ══════════════════════════════════════════════════════════════
#  MAIN TEST RUNNER
# ══════════════════════════════════════════════════════════════

def run_test(persona, script, max_turns=6, verbose=False, interactive=False, org_id=None, run_deepmost=True):
    """Run a full roleplay test session."""

    orchestrator = AgentOrchestrator()
    session_id = 99990 + persona.id

    hr("═")
    print(f"{BOLD}{CYAN}  🎭 ROLEPLAY TEST SESSION{RESET}")
    print(f"  Persona:    {BOLD}{persona.name}{RESET} ({persona.difficulty})")
    print(f"  Tone:       {persona.tone}")
    print(f"  Session ID: {session_id}")
    print(f"  RAG Docs:   {BOLD}{'org_id=' + str(org_id) if org_id else 'disabled'}{RESET}")
    if not interactive:
        print(f"  Turns:      {max_turns}")
    else:
        print(f"  Mode:       {BOLD}INTERACTIVE{RESET} (type 'quit' to end)")
    hr("═")
    print()

    messages = []  # Conversation history
    all_results = []
    turn = 0

    while True:
        turn += 1

        # Get trainee message
        if interactive:
            try:
                trainee_msg = input(f"{GREEN}{BOLD}You > {RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\nSession ended by user.")
                break
            if trainee_msg.lower() in ("quit", "exit", "end", "q"):
                break
            if not trainee_msg:
                continue
        else:
            if turn > max_turns or turn > len(script):
                break
            trainee_msg = script[turn - 1]
            print(f"{GREEN}{BOLD}You [{turn}] >{RESET} {trainee_msg}")

        # Call orchestrator
        try:
            result = orchestrator.process_message(
                persona=persona,
                messages=messages,
                trainee_message=trainee_msg,
                session_id=session_id,
                org_id=org_id,
                total_message_count=turn,
            )
        except Exception as e:
            print(f"{RED}  ❌ Orchestrator error: {e}{RESET}")
            import traceback
            traceback.print_exc()
            break

        ai_response = result["response"]
        all_results.append(result)

        # Print AI response
        print(f"{MAGENTA}{BOLD}AI [{turn}] >{RESET} {ai_response}")

        # Print agent outputs
        print_agent_outputs(result, verbose)
        print()

        # Update message history (mock the DB message format)
        messages.append(SimpleNamespace(
            sender="trainee", message_text=trainee_msg,
            sequence_number=turn * 2 - 1,
        ))
        messages.append(SimpleNamespace(
            sender="ai_customer", message_text=ai_response,
            sequence_number=turn * 2,
        ))

    # ── Post-session evaluation ──
    eval_data = None
    if len(messages) >= 6:
        print()
        hr()
        print(f"{DIM}  Running post-session evaluation...{RESET}")
        try:
            eval_data = orchestrator.process_evaluation(
                persona=persona,
                messages=messages,
                org_id=org_id,
                session_id=session_id,
            )
            print_evaluation(eval_data, verbose)
        except Exception as e:
            print(f"{RED}  ❌ Evaluation error: {e}{RESET}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n{DIM}  ⚠️  Need at least 3 exchanges (6 messages) for evaluation. Got {len(messages)}.{RESET}")

    # ── SalesRLAgent Conversion Analysis (replaces keyword model) ──
    if run_deepmost and len(messages) >= 6:
        print()
        hr()
        
        # Run SalesRLAgent
        deepmost_result = run_deepmost_prediction(messages)
        
        # Display full analysis
        if deepmost_result:
            print_salesrlagent_analysis(deepmost_result)
    elif not run_deepmost:
        print(f"\n{DIM}  Skipped SalesRLAgent conversion analysis (--no-deepmost){RESET}")

    # Clean up
    orchestrator.clear_session_cache(session_id)

    print(f"\n{DIM}  Session complete. {len(messages)} messages exchanged.{RESET}\n")


# ══════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Roleplay Test Runner — test the multi-agent pipeline without UI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_roleplay.py --auto                     # Auto-runs with random persona
  python test_roleplay.py --auto --persona 5         # Test "The Skeptic" (advanced)
  python test_roleplay.py --auto --turns 3 --verbose # Quick verbose test
  python test_roleplay.py --interactive              # Type your own messages
  python test_roleplay.py --interactive --persona 3  # Interactive with "Busy Executive"
  python test_roleplay.py --list                     # List all available personas
        """,
    )
    parser.add_argument("--auto", action="store_true", help="Auto-play with predefined sales script")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode — type your own messages")
    parser.add_argument("--persona", "-p", type=int, default=None, help="Persona number (1-8), see --list")
    parser.add_argument("--turns", "-t", type=int, default=6, help="Max turns in auto mode (default: 6)")
    parser.add_argument("--org-id", type=int, default=None, help="Organization ID for RAG document retrieval")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed agent outputs")
    parser.add_argument("--no-deepmost", action="store_true", help="Skip SalesRLAgent post-session comparison")
    parser.add_argument("--list", "-l", action="store_true", help="List all available personas and exit")
    args = parser.parse_args()

    # List personas
    if args.list:
        print(f"\n{BOLD}Available Personas:{RESET}\n")
        for p in PERSONAS:
            diff_color = GREEN if p.difficulty == "beginner" else YELLOW if p.difficulty == "intermediate" else RED
            print(f"  {BOLD}{p.id}.{RESET} {p.name:30s} {diff_color}[{p.difficulty}]{RESET}  {DIM}{p.description[:50]}...{RESET}")
        print()
        return

    # Default to --auto if neither specified
    if not args.auto and not args.interactive:
        args.auto = True

    # Select persona
    if args.persona:
        if 1 <= args.persona <= len(PERSONAS):
            persona = PERSONAS[args.persona - 1]
        else:
            print(f"Invalid persona number. Use 1-{len(PERSONAS)}. Run with --list to see options.")
            return
    else:
        import random
        persona = random.choice(PERSONAS)
        print(f"{DIM}  Randomly selected persona: {persona.name}{RESET}")

    # Select script
    difficulty = persona.difficulty
    script = SALES_SCRIPTS.get(difficulty, SALES_SCRIPTS["intermediate"])

    # RUN
    run_test(
        persona=persona,
        script=script,
        max_turns=min(args.turns, len(script)),
        verbose=args.verbose,
        interactive=args.interactive,
        org_id=args.org_id,
        run_deepmost=not args.no_deepmost,
    )


if __name__ == "__main__":
    main()
