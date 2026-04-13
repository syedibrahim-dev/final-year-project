"""
Benchmark: SalesRLAgent conversion prediction accuracy.
Tests with the outcome metric fix applied.
"""
import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "conversion"))

from deepmost import sales
from ollama_llm_proxy import OllamaLLMProxy

# ── Setup agent with outcome patch ──
agent = sales.Agent(
    model_path="https://huggingface.co/DeepMostInnovations/sales-conversion-model-reinf-learning/resolve/main/sales_conversion_model.zip",
    llm_model=None, use_gpu=False, auto_download=True,
)
proxy = OllamaLLMProxy(model="llama3.1:8b-instruct-q8_0")
agent.predictor.embedding_provider.llm = proxy

# Patch outcome metric
_original_analyze = agent.predictor.embedding_provider.analyze_metrics
def _patched_analyze(history, turn_number):
    metrics = _original_analyze(history, turn_number)
    eng = metrics.get("customer_engagement", 0.5)
    eff = metrics.get("sales_effectiveness", 0.5)
    urg = metrics.get("urgency_level", 0.3)
    obj = metrics.get("objection_count", 0.3)
    auth = metrics.get("decision_authority_signals", 0.3)
    price = metrics.get("pricing_sensitivity", 0.5)
    outcome = (eng*0.30 + eff*0.25 + urg*0.15 + auth*0.10 + (1-obj)*0.10 + (1-price)*0.10)
    metrics["outcome"] = round(max(0.0, min(1.0, outcome)), 3)
    return metrics
agent.predictor.embedding_provider.analyze_metrics = _patched_analyze

print("Agent loaded with outcome fix\n")

# ── Test conversations with known expected outcomes ──
TESTS = [
    {"name": "Strong positive - demo scheduled", "expected": "high", "messages": [
        {"speaker": "sales_rep", "message": "Thanks for your time today. We help companies automate certificate management."},
        {"speaker": "customer", "message": "That sounds interesting. We have been struggling with expired certs."},
        {"speaker": "sales_rep", "message": "How often do certificates expire unexpectedly for your team?"},
        {"speaker": "customer", "message": "At least twice a quarter. It causes outages and we scramble to fix them."},
        {"speaker": "sales_rep", "message": "Our platform auto-renews with 99.7 percent success rate. Clients see 85 percent fewer outages."},
        {"speaker": "customer", "message": "That would save us a lot of headaches. What does it cost?"},
        {"speaker": "sales_rep", "message": "The Professional plan is 79 dollars per month. Most clients see ROI in 3 months."},
        {"speaker": "customer", "message": "That sounds reasonable. Can we schedule a demo next week?"},
    ]},
    {"name": "Negative - brushed off", "expected": "low", "messages": [
        {"speaker": "sales_rep", "message": "Hi, I wanted to tell you about our certificate management platform."},
        {"speaker": "customer", "message": "We are not really looking at this right now."},
        {"speaker": "sales_rep", "message": "I understand. Can I ask what you currently use?"},
        {"speaker": "customer", "message": "We handle it internally and it works fine. Not interested."},
        {"speaker": "sales_rep", "message": "What if I could show you how to save time?"},
        {"speaker": "customer", "message": "Look, I appreciate the call but we are good. Send me an email if you want."},
    ]},
    {"name": "Medium - budget concern", "expected": "medium", "messages": [
        {"speaker": "sales_rep", "message": "Thanks for chatting. What challenges do you face with certificate management?"},
        {"speaker": "customer", "message": "Honestly its a pain. We lost a client last month because of an expired cert."},
        {"speaker": "sales_rep", "message": "That is exactly the problem we solve. Our platform automates the entire lifecycle."},
        {"speaker": "customer", "message": "Sounds useful but our budget is really tight this quarter. What does it cost?"},
        {"speaker": "sales_rep", "message": "Starting at 29 dollars a month. We also have a free trial."},
        {"speaker": "customer", "message": "I need to think about it and check with my boss. Can you send me some info?"},
    ]},
    {"name": "Very positive - ready to buy", "expected": "high", "messages": [
        {"speaker": "sales_rep", "message": "Hi, thanks for jumping on the call."},
        {"speaker": "customer", "message": "Yeah, we have been looking for exactly this kind of solution."},
        {"speaker": "sales_rep", "message": "Tell me about your current setup."},
        {"speaker": "customer", "message": "We manage 500 certs manually. Its a nightmare and we had 3 outages last year."},
        {"speaker": "sales_rep", "message": "With our Enterprise plan you get unlimited certs, auto-renewal, and a dedicated account manager."},
        {"speaker": "customer", "message": "That is exactly what we need. What is the pricing and how fast can we get started?"},
        {"speaker": "sales_rep", "message": "I can get you a custom quote by tomorrow and we can deploy within 3 weeks."},
        {"speaker": "customer", "message": "Perfect. Send the quote to my email and copy my CTO. We want to move fast on this."},
    ]},
    {"name": "Hostile - angry customer", "expected": "low", "messages": [
        {"speaker": "sales_rep", "message": "Hi, is this a good time to discuss our platform?"},
        {"speaker": "customer", "message": "You are the third vendor to call me this week. I am not interested."},
        {"speaker": "sales_rep", "message": "I understand. Just 2 minutes to explain how we are different?"},
        {"speaker": "customer", "message": "No. Every vendor says they are different. Take me off your list."},
    ]},
    {"name": "Warm lead - needs follow-up", "expected": "medium", "messages": [
        {"speaker": "sales_rep", "message": "Good morning. I noticed your company recently expanded to 3 new regions."},
        {"speaker": "customer", "message": "Yeah, growth has been crazy. Why do you ask?"},
        {"speaker": "sales_rep", "message": "More regions means more certificates to manage. How are you handling that?"},
        {"speaker": "customer", "message": "Honestly we are just winging it. Our IT team is overwhelmed."},
        {"speaker": "sales_rep", "message": "We specialize in automating that. Would a 15 minute call next week be useful?"},
        {"speaker": "customer", "message": "Maybe. Send me some info first and I will take a look before committing to anything."},
    ]},
    {"name": "Enterprise - multi-stakeholder", "expected": "high", "messages": [
        {"speaker": "sales_rep", "message": "Thanks for connecting me with your security team as well."},
        {"speaker": "customer", "message": "No problem. We all need to be aligned on this decision."},
        {"speaker": "sales_rep", "message": "Absolutely. For security, we are SOC 2 Type II certified with AES-256 encryption."},
        {"speaker": "customer", "message": "Good. Our CISO was asking about that specifically."},
        {"speaker": "sales_rep", "message": "For IT, deployment takes 3 weeks and we handle migration. For finance, ROI within 3 months."},
        {"speaker": "customer", "message": "This checks a lot of boxes. Can you send a proposal we can circulate internally?"},
        {"speaker": "sales_rep", "message": "Absolutely. I will have it to you by Friday with everything discussed today."},
        {"speaker": "customer", "message": "Great. We have a budget review next month and I want this on the agenda."},
    ]},
    {"name": "Complete rejection - competitor locked", "expected": "low", "messages": [
        {"speaker": "sales_rep", "message": "Hi, I help companies with certificate lifecycle management."},
        {"speaker": "customer", "message": "We just signed a 3 year contract with your competitor last month."},
        {"speaker": "sales_rep", "message": "I see. What made you choose them?"},
        {"speaker": "customer", "message": "Price and they already integrate with our stack. No reason to look elsewhere."},
    ]},
]

print(f"Running {len(TESTS)} test conversations...\n")
print(f"{'RESULT':7s} | {'CONVERSATION':45s} | {'EXPECTED':8s} | {'PROB':6s} | {'OUTCOME':7s} | {'ENG':5s} | {'EFF':5s}")
print("-" * 110)

correct = 0
total = len(TESTS)

for test in TESTS:
    result = agent.predictor.predict_conversion(
        conversation_history=test["messages"],
        conversation_id=test["name"],
        is_incremental_prediction=True,
    )
    raw_prob = result["probability"]
    expected = test["expected"]
    metrics = result.get("metrics", {})

    # Apply same calibration as deepmost_predictor.py
    outcome = metrics.get("outcome", 0.5)
    engagement = metrics.get("customer_engagement", 0.5)
    ppo_rescaled = max(0.0, min(1.0, (raw_prob - 0.12) / 0.18))
    prob = round(max(0.0, min(1.0, ppo_rescaled * 0.40 + outcome * 0.35 + engagement * 0.25)), 4)

    # Scoring thresholds
    if expected == "high" and prob >= 0.60:
        match = "CORRECT"; correct += 1
    elif expected == "low" and prob < 0.30:
        match = "CORRECT"; correct += 1
    elif expected == "medium" and 0.30 <= prob <= 0.60:
        match = "CORRECT"; correct += 1
    else:
        match = "MISS"

    def fmt(v):
        return f"{v:.2f}" if isinstance(v, float) else "?"

    print(f"{match:7s} | {test['name']:45s} | {expected:8s} | {prob:.3f}  | {fmt(metrics.get('outcome'))}   | {fmt(metrics.get('customer_engagement'))} | {fmt(metrics.get('sales_effectiveness'))}")

print("-" * 110)
print(f"\nACCURACY: {correct}/{total} = {correct/total*100:.0f}%")
print(f"\nComparison:")
print(f"  Paper (Azure + full pipeline):    96.7%")
print(f"  Before outcome fix (BGE-M3):       40%")
print(f"  After outcome fix (this run):      {correct/total*100:.0f}%")
