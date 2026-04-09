"""
Deepmost SalesRLAgent Predictor — Full Integration

Supports two modes:
  1. --file mode (original):  Batch analysis on a saved transcript JSON.
  2. --server mode (new):     Persistent process that stays alive, accepts
                              incremental predictions via stdin/stdout JSON
                              protocol.  Uses OllamaLLMProxy so the Qwen3-4B
                              LLM runs through Ollama (GPU-managed) instead
                              of loading a second GGUF into VRAM.

Usage:
    # Batch (unchanged)
    python deepmost_predictor.py --file transcript.json [--chart chart.png]

    # Persistent server (called by services/conversion_service.py)
    python deepmost_predictor.py --server [--ollama-model qwen3:4b]
"""

import sys
import json
import argparse
import io
import os
import re
import logging

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Redirect all logging to stderr so stdout is clean JSON only
logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
logger = logging.getLogger(__name__)


# ── Shared agent singleton ───────────────────────────────────────────

_agent = None
_agent_mode = None  # "local_llm" or "ollama"


def _get_agent(ollama_model=None):
    """
    Lazily initialise the deepmost Agent.

    If ollama_model is provided, the agent is created WITHOUT a llm_model
    and then its embedding_provider.llm is monkey-patched with OllamaLLMProxy.
    """
    global _agent, _agent_mode
    if _agent is not None:
        return _agent

    from deepmost import sales

    model_url = (
        "https://huggingface.co/DeepMostInnovations/"
        "sales-conversion-model-reinf-learning/resolve/main/"
        "sales_conversion_model.zip"
    )

    if ollama_model:
        # ── Ollama-routed mode ──
        # Create agent WITHOUT llm_model so it doesn't load Qwen3-4B via llama-cpp.
        # The PPO model + BGE-M3 embeddings still load normally.
        _agent = sales.Agent(
            model_path=model_url,
            llm_model=None,       # don't load GGUF
            use_gpu=False,        # keep BGE-M3 on CPU (GPU reserved for Ollama)
            auto_download=True,
        )
        # Monkey-patch: inject OllamaLLMProxy as the LLM backend
        # This file lives next to us in conversion/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        from ollama_llm_proxy import OllamaLLMProxy

        proxy = OllamaLLMProxy(model=ollama_model)
        _agent.predictor.embedding_provider.llm = proxy

        # ── Fix: patch analyze_metrics to compute 'outcome' from LLM signals ──
        # The deepmost library hardcodes outcome=0.5 in all embedding providers.
        # This patch computes it from the metrics the LLM already returns,
        # giving the PPO model its most important input.
        _original_analyze = _agent.predictor.embedding_provider.analyze_metrics

        def _patched_analyze(history, turn_number):
            metrics = _original_analyze(history, turn_number)
            # Compute outcome from engagement, effectiveness, and other signals
            engagement = metrics.get("customer_engagement", 0.5)
            effectiveness = metrics.get("sales_effectiveness", 0.5)
            urgency = metrics.get("urgency_level", 0.3)
            objections = metrics.get("objection_count", 0.3)
            authority = metrics.get("decision_authority_signals", 0.3)
            pricing_sens = metrics.get("pricing_sensitivity", 0.5)
            # Weighted combination: engagement and effectiveness are strongest signals
            outcome = (
                engagement * 0.30
                + effectiveness * 0.25
                + urgency * 0.15
                + authority * 0.10
                + (1.0 - objections) * 0.10  # fewer objections = better
                + (1.0 - pricing_sens) * 0.10  # less price sensitivity = better
            )
            metrics["outcome"] = round(max(0.0, min(1.0, outcome)), 3)
            return metrics

        _agent.predictor.embedding_provider.analyze_metrics = _patched_analyze

        _agent_mode = "ollama"
        print(
            json.dumps({"status": "ready", "mode": "ollama", "llm": ollama_model}),
            flush=True,
        )
    else:
        # ── Original local GGUF mode ──
        _agent = sales.Agent(
            model_path=model_url,
            llm_model="unsloth/Qwen3-4B-GGUF",
            auto_download=True,
        )
        _agent_mode = "local_llm"

    return _agent


# ── Incremental single-turn prediction ──────────────────────────────

def predict_single_turn(agent, conversation_messages, conversation_id="live"):
    """
    Run a single incremental prediction on the conversation so far.
    Much faster than analyze_conversation_progression (which replays
    every turn from scratch).

    Returns a dict compatible with the orchestrator's conversion_data shape.
    """
    # Normalise to deepmost's expected format
    normalized = []
    for msg in conversation_messages:
        sender = msg.get("sender", msg.get("speaker", "unknown"))
        text = msg.get("text", msg.get("message", ""))
        # Map our sender names to deepmost's expected names
        if sender in ("trainee", "sales_rep", "salesperson"):
            speaker = "sales_rep"
        else:
            speaker = "customer"
        normalized.append({"speaker": speaker, "message": text})

    if not normalized:
        return {"probability": 0.5, "status": "Unknown", "metrics": {}}

    result = agent.predictor.predict_conversion(
        conversation_history=normalized,
        conversation_id=conversation_id,
        is_incremental_prediction=True,
    )

    raw_prob = float(result.get("probability", 0.5))
    metrics = result.get("metrics", {})

    # ── Calibrated probability ──
    # The PPO model with BGE-M3 embeddings outputs a compressed range (~0.15-0.25)
    # instead of the full 0-1 range it was trained for with Azure OpenAI embeddings.
    # We blend the raw PPO output with the LLM-computed outcome metric to produce
    # a more useful probability estimate.
    #
    # The LLM metrics (engagement, effectiveness, outcome) correctly differentiate
    # positive vs negative conversations. The PPO adds sequential/embedding awareness.
    outcome = metrics.get("outcome", 0.5)
    engagement = metrics.get("customer_engagement", 0.5)

    # Blend: 40% PPO (rescaled), 35% outcome, 25% engagement
    # PPO rescale: map observed range [0.12, 0.30] → [0.05, 0.85]
    ppo_rescaled = max(0.0, min(1.0, (raw_prob - 0.12) / 0.18))
    calibrated = ppo_rescaled * 0.40 + outcome * 0.35 + engagement * 0.25
    calibrated = round(max(0.0, min(1.0, calibrated)), 4)

    # Determine status from calibrated probability
    if calibrated >= 0.70:
        status = "Hot Lead"
    elif calibrated >= 0.50:
        status = "Warm Lead"
    elif calibrated >= 0.30:
        status = "Cool Lead"
    else:
        status = "Cold Lead"

    return {
        "probability": calibrated,
        "raw_ppo_probability": round(raw_prob, 4),
        "status": status,
        "turn": result.get("turn", len(normalized)),
        "metrics": metrics,
        "backend": result.get("backend", _agent_mode),
    }


# ── Full post-session analysis (original, kept for --file mode) ──────

def run_prediction(conversation_messages, chart_path=None):
    """
    Run full SalesRLAgent analysis on a conversation transcript.

    Returns dict with:
      - turn_predictions: list of per-turn data
      - turning_points: list of significant probability shifts
      - coaching_suggestions: list of actionable coaching tips
      - final_probability / final_status
      - chart_path: path to saved trend chart (if requested)
    """
    agent = _get_agent()

    flat_messages = [msg['text'] for msg in conversation_messages]

    # Capture stdout
    old_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    results = agent.analyze_conversation_progression(flat_messages, print_results=True)
    sys.stdout = old_stdout
    printed_output = captured.getvalue()

    # ── Parse turn predictions ──
    turn_predictions = []

    if isinstance(results, (list, tuple)):
        for item in results:
            if isinstance(item, dict):
                turn_predictions.append({
                    'turn': item.get('turn', len(turn_predictions) + 1),
                    'speaker': item.get('speaker', 'unknown'),
                    'probability': round(float(item.get('probability', item.get('conversion_probability', 0.5))), 4),
                    'message_preview': (item.get('message', '')[:80] + '...') if len(item.get('message', '')) > 80 else item.get('message', ''),
                    'metrics': item.get('metrics', {}),
                })
    elif isinstance(results, dict):
        turns_data = (
            results.get('turns', []) or results.get('progression', []) or
            results.get('turn_results', []) or results.get('results', [])
        )
        if isinstance(turns_data, list):
            for item in turns_data:
                if isinstance(item, dict):
                    turn_predictions.append({
                        'turn': item.get('turn', len(turn_predictions) + 1),
                        'speaker': item.get('speaker', 'unknown'),
                        'probability': round(float(item.get('probability', 0.5)), 4),
                        'message_preview': (item.get('message', '')[:80] + '...') if len(item.get('message', '')) > 80 else item.get('message', ''),
                        'metrics': item.get('metrics', {}),
                    })

    # Fallback: parse from printed output
    if not turn_predictions and printed_output:
        for line in printed_output.split('\n'):
            match = re.search(r'Turn\s+(\d+)\s+\((\w+)\):\s+"(.+?)"\s+->\s+Probability:\s+([\d.]+)', line)
            if match:
                turn_predictions.append({
                    'turn': int(match.group(1)),
                    'speaker': match.group(2),
                    'probability': round(float(match.group(4)), 4),
                    'message_preview': (match.group(3)[:80] + '...') if len(match.group(3)) > 80 else match.group(3),
                    'metrics': {},
                })

    # ── Final probability ──
    final_probability = 0.5
    final_status = "Unknown"

    if isinstance(results, dict):
        final_probability = float(results.get('final_probability', results.get('probability', 0.5)))
        final_status = results.get('final_status', results.get('status', 'Unknown'))
    elif turn_predictions:
        final_probability = turn_predictions[-1]['probability']

    final_match = re.search(r'Final Conversion Probability:\s+([\d.]+)%', printed_output)
    if final_match:
        final_probability = round(float(final_match.group(1)) / 100.0, 4)
    status_match = re.search(r'Final Status:\s+(.+)', printed_output)
    if status_match:
        final_status = status_match.group(1).strip()

    # ── Turning Point Analysis ──
    turning_points = []
    for i in range(1, len(turn_predictions)):
        prev_prob = turn_predictions[i-1]['probability']
        curr_prob = turn_predictions[i]['probability']
        change = curr_prob - prev_prob

        turning_points.append({
            'turn': turn_predictions[i]['turn'],
            'speaker': turn_predictions[i]['speaker'],
            'change': round(change, 4),
            'direction': 'up' if change > 0 else 'down' if change < 0 else 'flat',
            'magnitude': abs(change),
            'message_preview': turn_predictions[i].get('message_preview', ''),
        })

    significant_turns = sorted(turning_points, key=lambda x: x['magnitude'], reverse=True)[:5]

    # ── Metrics-Based Coaching ──
    coaching_suggestions = []
    if turn_predictions:
        last_turn = turn_predictions[-1]
        metrics = last_turn.get('metrics', {})

        engagement = metrics.get('customer_engagement', None)
        if engagement is not None and engagement < 0.5:
            coaching_suggestions.append({
                'type': 'engagement',
                'suggestion': 'Customer engagement is low. Ask open-ended questions to draw them in.',
                'metric_value': round(engagement, 2),
            })

        effectiveness = metrics.get('sales_effectiveness', None)
        if effectiveness is not None and effectiveness < 0.5:
            coaching_suggestions.append({
                'type': 'effectiveness',
                'suggestion': 'Sales effectiveness is low. Focus on value proposition and benefits.',
                'metric_value': round(effectiveness, 2),
            })

        if final_probability < 0.3:
            coaching_suggestions.append({
                'type': 'probability',
                'suggestion': 'Deal probability is very low. Consider a different approach or re-engage.',
                'metric_value': round(final_probability, 2),
            })
        elif final_probability < 0.5:
            coaching_suggestions.append({
                'type': 'probability',
                'suggestion': 'Deal is on the fence. Focus on addressing objections and providing evidence.',
                'metric_value': round(final_probability, 2),
            })
        elif final_probability >= 0.7:
            coaching_suggestions.append({
                'type': 'probability',
                'suggestion': 'Strong conversion signal! Push for a commitment or next steps.',
                'metric_value': round(final_probability, 2),
            })

        if len(turn_predictions) >= 3:
            recent = [t['probability'] for t in turn_predictions[-3:]]
            if all(recent[i] < recent[i-1] for i in range(1, len(recent))):
                coaching_suggestions.append({
                    'type': 'trend',
                    'suggestion': 'Probability is declining. Reassess approach.',
                    'metric_value': None,
                })
            elif all(recent[i] > recent[i-1] for i in range(1, len(recent))):
                coaching_suggestions.append({
                    'type': 'trend',
                    'suggestion': 'Strong upward trend — maintain current approach.',
                    'metric_value': None,
                })

    # ── Trend Visualization ──
    saved_chart_path = None
    if chart_path and turn_predictions:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            turns = [t['turn'] for t in turn_predictions]
            probs = [t['probability'] for t in turn_predictions]

            fig, ax = plt.subplots(figsize=(12, 5))
            ax.axhspan(0, 0.3, alpha=0.08, color='red', label='Low')
            ax.axhspan(0.3, 0.6, alpha=0.08, color='orange', label='Medium')
            ax.axhspan(0.6, 1.0, alpha=0.08, color='green', label='High')
            ax.plot(turns, probs, 'o-', color='#2196F3', linewidth=2.5, markersize=8, label='Conversion Probability')

            for tp in significant_turns[:3]:
                tp_turn = tp['turn']
                if tp_turn <= len(probs):
                    tp_prob = probs[tp_turn - 1]
                    arrow = 'up' if tp['direction'] == 'up' else 'down'
                    color = 'green' if tp['direction'] == 'up' else 'red'
                    ax.annotate(
                        f"{arrow} {tp['change']:+.1%}",
                        xy=(tp_turn, tp_prob),
                        xytext=(0, 15 if tp['direction'] == 'up' else -20),
                        textcoords='offset points',
                        fontsize=9, fontweight='bold', color=color,
                        ha='center',
                    )

            for t in turn_predictions:
                marker_color = '#4CAF50' if t['speaker'] in ('sales_rep', 'trainee') else '#FF9800'
                ax.plot(t['turn'], t['probability'], 'o', color=marker_color, markersize=10, zorder=5)

            ax.set_xlabel('Conversation Turn', fontsize=12)
            ax.set_ylabel('Conversion Probability', fontsize=12)
            ax.set_title('SalesRLAgent - Conversion Probability Trajectory', fontsize=14, fontweight='bold')
            ax.set_ylim(-0.05, 1.05)
            ax.set_xlim(0.5, max(turns) + 0.5)
            ax.legend(loc='upper left', fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.axhline(y=final_probability, color='#2196F3', linestyle='--', alpha=0.5)
            ax.text(max(turns) + 0.3, final_probability, f'Final: {final_probability:.1%}',
                    fontsize=10, color='#2196F3', va='center')
            plt.tight_layout()
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            saved_chart_path = chart_path
        except Exception:
            saved_chart_path = None

    return {
        'model': 'SalesRLAgent (Deepmost)',
        'paper': 'arXiv:2503.23303',
        'llm_backend': f'Ollama {_agent_mode}' if _agent_mode == 'ollama' else 'Qwen3-4B-GGUF (local)',
        'turn_predictions': turn_predictions,
        'turning_points': turning_points,
        'significant_turns': significant_turns,
        'coaching_suggestions': coaching_suggestions,
        'final_probability': final_probability,
        'final_status': final_status,
        'total_turns': len(flat_messages),
        'chart_path': saved_chart_path,
    }


# ── Server mode: persistent stdin/stdout JSON protocol ──────────────

def run_server(ollama_model):
    """
    Persistent server mode.  Reads one JSON request per line from stdin,
    writes one JSON response per line to stdout.

    Protocol:
      Request:  {"action": "predict", "conversation_id": "...", "messages": [...]}
      Response: {"probability": 0.62, "status": "Warm Lead", ...}

      Request:  {"action": "ping"}
      Response: {"status": "ok"}

      Request:  {"action": "shutdown"}
      → process exits
    """
    # Force all library output to stderr
    import warnings
    warnings.filterwarnings("ignore")

    # Initialise agent (loads PPO + BGE-M3, patches LLM with Ollama proxy)
    agent = _get_agent(ollama_model=ollama_model)

    # Read requests from stdin, one JSON per line
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            _respond({"error": f"Invalid JSON: {e}"})
            continue

        action = request.get("action", "predict")

        if action == "ping":
            _respond({"status": "ok"})

        elif action == "shutdown":
            _respond({"status": "shutting_down"})
            break

        elif action == "predict":
            messages = request.get("messages", [])
            conv_id = request.get("conversation_id", "live")
            try:
                result = predict_single_turn(agent, messages, conv_id)
                _respond(result)
            except Exception as e:
                logger.error(f"Prediction failed: {e}", exc_info=True)
                _respond({"error": str(e), "probability": 0.5})

        elif action == "analyze_full":
            messages = request.get("messages", [])
            try:
                result = run_prediction(messages, chart_path=None)
                _respond(result)
            except Exception as e:
                logger.error(f"Full analysis failed: {e}", exc_info=True)
                _respond({"error": str(e)})

        else:
            _respond({"error": f"Unknown action: {action}"})


def _respond(data):
    """Write a single JSON line to stdout and flush."""
    sys.stdout.write(json.dumps(data, default=str) + "\n")
    sys.stdout.flush()


# ── CLI entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SalesRLAgent Conversion Predictor")
    parser.add_argument('--file', '-f', type=str, default=None, help='Path to JSON transcript')
    parser.add_argument('--chart', '-c', type=str, default=None, help='Path to save trend chart PNG')
    parser.add_argument('--server', action='store_true', help='Run in persistent server mode')
    parser.add_argument('--ollama-model', type=str, default='qwen3:4b',
                        help='Ollama model for LLM metrics (server mode)')
    args = parser.parse_args()

    if args.server:
        run_server(args.ollama_model)
    elif args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        messages = data if isinstance(data, list) else data.get('messages', [])
        result = run_prediction(messages, chart_path=args.chart)
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.error("Either --file or --server is required")


if __name__ == "__main__":
    main()
