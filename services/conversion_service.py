"""
Conversion Service — manages the SalesRLAgent (deepmost) subprocess.

Launches conversion/deepmost_predictor.py in --server mode as a persistent
subprocess.  The deepmost process keeps its PPO model + BGE-M3 embeddings
loaded, and routes LLM calls through Ollama (same Llama 3.1 8B model used
for roleplay — no GPU swap needed).

Predictions run ASYNCHRONOUSLY in a background thread so they never block
the roleplay response.  The orchestrator receives the most recent available
prediction (which may be from the previous turn).

Public API:
    get_conversion_service()  → ConversionService singleton
    service.predict_async(session_id, messages)  → fires background prediction
    service.get_latest(session_id)               → returns last available result
    service.shutdown()
"""

import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEEPMOST_SCRIPT = str(_PROJECT_ROOT / "conversion" / "deepmost_predictor.py")


class ConversionService:
    """
    Manages a persistent deepmost_predictor.py subprocess with async predictions.
    """

    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._ready = False
        # Per-session state
        self._session_history: Dict[int, List[Dict]] = {}
        self._latest_result: Dict[int, Dict] = {}
        self._pending: Dict[int, bool] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────

    def _ensure_running(self) -> bool:
        """Start the subprocess if it isn't running."""
        if self._process and self._process.poll() is None and self._ready:
            return True

        python_exe = getattr(settings, "SALESRL_PYTHON", "")
        if not python_exe or not Path(python_exe).exists():
            logger.warning(f"SalesRLAgent Python not found: {python_exe}")
            return False

        ollama_model = getattr(settings, "SALESRL_LLM_MODEL", "llama3.1:8b-instruct-q4_K_M")

        logger.info("Starting SalesRLAgent subprocess...")
        try:
            self._process = subprocess.Popen(
                [
                    python_exe,
                    _DEEPMOST_SCRIPT,
                    "--server",
                    "--ollama-model", ollama_model,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(_PROJECT_ROOT),
            )
        except Exception as e:
            logger.error(f"Failed to start SalesRLAgent subprocess: {e}")
            return False

        try:
            ready_line = self._process.stdout.readline()
            if not ready_line:
                stderr_out = self._process.stderr.read(500) if self._process.stderr else ""
                logger.error(f"SalesRLAgent no output. stderr: {stderr_out}")
                return False

            ready_msg = json.loads(ready_line.strip())
            if ready_msg.get("status") == "ready":
                self._ready = True
                logger.info(
                    f"SalesRLAgent ready (mode={ready_msg.get('mode')}, "
                    f"llm={ready_msg.get('llm')})"
                )
                return True
            else:
                logger.error(f"Unexpected ready message: {ready_msg}")
                return False
        except Exception as e:
            logger.error(f"SalesRLAgent startup failed: {e}")
            return False

    def _send_request(self, request: dict) -> Optional[dict]:
        """Send a JSON request and read the response.  Thread-safe."""
        with self._lock:
            if not self._ensure_running():
                return None
            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()

                response_line = self._process.stdout.readline()
                if not response_line:
                    logger.error("SalesRLAgent returned empty response")
                    self._ready = False
                    return None

                return json.loads(response_line.strip())
            except (BrokenPipeError, OSError) as e:
                logger.error(f"SalesRLAgent pipe broken: {e}")
                self._ready = False
                return None
            except json.JSONDecodeError as e:
                logger.error(f"SalesRLAgent invalid JSON: {e}")
                return None

    # ── Async prediction ──────────────────────────────────────────────

    def _run_prediction_bg(self, session_id: int, formatted: List[Dict]):
        """Background thread: run prediction and store result."""
        try:
            result = self._send_request({
                "action": "predict",
                "conversation_id": str(session_id),
                "messages": formatted,
            })

            if result and "error" not in result:
                history = self._session_history.setdefault(session_id, [])
                history.append(result)
                result["trend"] = self._calculate_trend(history)
                result["momentum"] = self._calculate_momentum(history)
                result["turning_points"] = self._detect_turning_points(history)
                self._latest_result[session_id] = result
                logger.info(
                    f"SalesRL prediction complete: prob={result.get('probability')} "
                    f"trend={result.get('trend')}"
                )
            else:
                logger.warning(f"SalesRL prediction returned: {result}")
        except Exception as e:
            logger.error(f"SalesRL background prediction failed: {e}")
        finally:
            self._pending.pop(session_id, None)

    def predict_async(
        self,
        session_id: int,
        messages: List[Dict[str, str]],
    ):
        """
        Fire a prediction in the background.  Non-blocking.
        Result will be available via get_latest() when ready.
        """
        if not getattr(settings, "ENABLE_SALESRL_AGENT", False):
            return

        # Don't queue if a prediction is already running for this session
        if self._pending.get(session_id):
            return

        formatted = []
        for msg in messages:
            sender = msg.get("sender", "")
            text = msg.get("text", msg.get("message_text", ""))
            if sender and text:
                formatted.append({"sender": sender, "text": text})

        if len(formatted) < 2:
            return

        self._pending[session_id] = True
        thread = threading.Thread(
            target=self._run_prediction_bg,
            args=(session_id, formatted),
            daemon=True,
        )
        thread.start()

    def get_latest(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Return the most recent prediction for this session.
        May be from the current or previous turn.
        """
        return self._latest_result.get(session_id)

    # ── Sync prediction (for testing) ─────────────────────────────────

    def predict(
        self,
        session_id: int,
        messages: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """Synchronous prediction.  Blocks until result is ready."""
        if not getattr(settings, "ENABLE_SALESRL_AGENT", False):
            return None

        formatted = []
        for msg in messages:
            sender = msg.get("sender", "")
            text = msg.get("text", msg.get("message_text", ""))
            if sender and text:
                formatted.append({"sender": sender, "text": text})

        if len(formatted) < 2:
            return None

        result = self._send_request({
            "action": "predict",
            "conversation_id": str(session_id),
            "messages": formatted,
        })

        if result and "error" not in result:
            history = self._session_history.setdefault(session_id, [])
            history.append(result)
            result["trend"] = self._calculate_trend(history)
            result["momentum"] = self._calculate_momentum(history)
            result["turning_points"] = self._detect_turning_points(history)
            self._latest_result[session_id] = result

        return result

    # ── Full post-session analysis ───────────────────────────────────

    def analyze_full_session(
        self,
        session_id: int,
        messages: List[Dict[str, str]],
    ) -> Optional[Dict[str, Any]]:
        """
        Run full turn-by-turn conversion analysis on the complete transcript.
        Synchronous — called at end of session during evaluation.

        Returns dict with turn_predictions, turning_points,
        coaching_suggestions, final_probability, etc.
        """
        if not getattr(settings, "ENABLE_SALESRL_AGENT", False):
            return None

        formatted = []
        for msg in messages:
            sender = msg.get("sender", "")
            text = msg.get("text", msg.get("message_text", ""))
            if sender and text:
                formatted.append({"sender": sender, "text": text})

        if len(formatted) < 4:
            return None

        result = self._send_request({
            "action": "analyze_full",
            "messages": formatted,
        })

        if result and "error" not in result:
            # Extract probabilities array for the frontend trajectory chart
            turn_preds = result.get("turn_predictions", [])
            result["probabilities"] = [t["probability"] for t in turn_preds]
            return result

        logger.warning(f"SalesRL full analysis returned: {result}")
        return None

    # ── Session + lifecycle ───────────────────────────────────────────

    def clear_session(self, session_id: int):
        self._session_history.pop(session_id, None)
        self._latest_result.pop(session_id, None)
        self._pending.pop(session_id, None)

    def ping(self) -> bool:
        result = self._send_request({"action": "ping"})
        return result is not None and result.get("status") == "ok"

    def shutdown(self):
        if self._process and self._process.poll() is None:
            try:
                self._send_request({"action": "shutdown"})
                self._process.wait(timeout=10)
            except Exception:
                self._process.kill()
            logger.info("SalesRLAgent subprocess stopped")
        self._ready = False

    # ── Trend analysis helpers ────────────────────────────────────────

    @staticmethod
    def _calculate_trend(history: List[Dict]) -> str:
        probs = [h.get("probability", 0.5) for h in history]
        if len(probs) < 2:
            return "neutral"
        recent = probs[-3:] if len(probs) >= 3 else probs
        if recent[-1] > recent[0] + 0.05:
            return "improving"
        elif recent[-1] < recent[0] - 0.05:
            return "declining"
        return "stable"

    @staticmethod
    def _calculate_momentum(history: List[Dict]) -> float:
        probs = [h.get("probability", 0.5) for h in history]
        if len(probs) < 2:
            return 0.0
        return round(probs[-1] - probs[-2], 4)

    @staticmethod
    def _detect_turning_points(history: List[Dict]) -> List[Dict]:
        probs = [h.get("probability", 0.5) for h in history]
        points = []
        for i in range(1, len(probs)):
            delta = probs[i] - probs[i - 1]
            if abs(delta) > 0.10:
                points.append({
                    "turn": i + 1,
                    "delta": round(delta, 4),
                    "direction": "positive" if delta > 0 else "negative",
                })
        return points


# ── Module-level singleton ────────────────────────────────────────────

_service_instance: Optional[ConversionService] = None


def get_conversion_service() -> ConversionService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ConversionService()
    return _service_instance
