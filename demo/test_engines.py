"""
Engine A + Engine B — Comprehensive Test Suite
Tests objection detection, active listening, empathy, and pressure
with realistic B2B sales conversation examples.
"""
import sys, os
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from roleplay.engines.intent_engine import (
    detect_objection,
    classify_objection_response,
    analyze_active_listening,
    run_intent_analysis,
)
from roleplay.engines.emotion_engine import (
    detect_empathy,
    classify_pressure_level,
    run_emotion_analysis,
)

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

def run_test(name, tests, test_fn):
    print(f"\n{BOLD}{CYAN}{'=' * 80}")
    print(f"  {name}")
    print(f"{'=' * 80}{RESET}\n")
    correct = 0
    total = len(tests)
    for i, test in enumerate(tests, 1):
        result = test_fn(test)
        passed = result["passed"]
        if passed:
            correct += 1
        icon = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {icon} Test {i}: {test['desc']}")
        for line in result["details"]:
            print(f"       {DIM}{line}{RESET}")
        print()
    color = GREEN if correct == total else YELLOW if correct >= total * 0.8 else RED
    print(f"  {color}{BOLD}Result: {correct}/{total} ({correct/total*100:.0f}%){RESET}\n")
    return correct, total


# ══════════════════════════════════════════════════════════════════
#  TEST 1: OBJECTION DETECTION (Engine A)
# ══════════════════════════════════════════════════════════════════

OBJECTION_TESTS = [
    # === TRUE OBJECTIONS (should detect) ===
    {"msg": "$79 a month is a bit steep for us right now.",
     "expected": True, "desc": "Price objection — direct"},
    {"msg": "That's more than what our competitor charges.",
     "expected": True, "desc": "Competitor price comparison"},
    {"msg": "I need to check with my boss before making any decisions.",
     "expected": True, "desc": "Authority — needs approval"},
    {"msg": "We're not really looking to change anything right now.",
     "expected": True, "desc": "Timing — not ready"},
    {"msg": "I'm not convinced this would actually solve our problem.",
     "expected": True, "desc": "Doubt — unconvinced of value"},
    {"msg": "What's the catch? There must be hidden fees somewhere.",
     "expected": True, "desc": "Trust — suspicion of hidden costs"},
    {"msg": "We already have a solution that works fine for us.",
     "expected": True, "desc": "Status quo — happy with current"},
    {"msg": "Can you just send me an email? I don't have time for this.",
     "expected": True, "desc": "Dismissive brush-off"},
    {"msg": "How do I know this won't end up like the last software we tried that nobody used?",
     "expected": True, "desc": "Past bad experience — risk aversion"},
    {"msg": "The implementation timeline seems too long for our needs.",
     "expected": True, "desc": "Timeline objection"},
    {"msg": "I'd need to see some real case studies before I could take this seriously.",
     "expected": True, "desc": "Evidence — wants proof"},
    {"msg": "Your competitor offered us the same thing for 40% less.",
     "expected": True, "desc": "Competitive displacement — specific number"},

    # === NOT OBJECTIONS (should not detect) ===
    {"msg": "That sounds really interesting. Tell me more about how it works.",
     "expected": False, "desc": "Genuine interest"},
    {"msg": "Can you walk me through the deployment process step by step?",
     "expected": False, "desc": "Information request — process question"},
    {"msg": "We manage about 200 certificates across three cloud providers.",
     "expected": False, "desc": "Factual statement — situation info"},
    {"msg": "Sure, let's schedule a demo for next Tuesday.",
     "expected": False, "desc": "Agreement — scheduling"},
    {"msg": "Our IT team has been struggling with this exact problem.",
     "expected": False, "desc": "Pain point sharing — not objecting"},
    {"msg": "What integrations do you support out of the box?",
     "expected": False, "desc": "Technical question"},
    {"msg": "That 99.7% renewal rate is impressive. How do you achieve that?",
     "expected": False, "desc": "Positive inquiry about a claim"},
    {"msg": "Good morning! Thanks for taking my call.",
     "expected": False, "desc": "Greeting — neutral"},
]

def test_objection(test):
    is_obj, conf = detect_objection(test["msg"])
    passed = is_obj == test["expected"]
    return {
        "passed": passed,
        "details": [
            f"Message: \"{test['msg'][:70]}\"",
            f"Expected: {test['expected']}, Got: {is_obj} (conf: {conf:.2f})",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  TEST 2: OBJECTION HANDLING CLASSIFICATION (Engine A)
# ══════════════════════════════════════════════════════════════════

HANDLING_TESTS = [
    # === RESOLVED ===
    {"msg": "I understand your concern about pricing. For companies your size, the Professional plan at $79 per month typically pays for itself within 3 months through reduced incident costs.",
     "expected": "resolved", "desc": "Acknowledged + specific solution with ROI"},
    {"msg": "That's a fair point about the timeline. We actually have an expedited deployment option that cuts it down to 10 days with a dedicated engineer.",
     "expected": "resolved", "desc": "Acknowledged + offered alternative"},
    {"msg": "You're right to ask about case studies. Let me share three examples from manufacturing companies similar to yours.",
     "expected": "resolved", "desc": "Validated concern + provided evidence"},

    # === DEFLECTED ===
    {"msg": "Sure, but let me first tell you about our new AI features that launched last month.",
     "expected": "deflected", "desc": "Changed subject to features"},
    {"msg": "A lot of our customers had the same concern initially. Anyway, the platform also has real-time monitoring.",
     "expected": "deflected", "desc": "Dismissed concern, pivoted to features"},
    {"msg": "I can send you some information about that. In the meantime, have you seen our demo video?",
     "expected": "deflected", "desc": "Deferred + redirected"},

    # === ESCALATED ===
    {"msg": "Look, if you can't afford $79 a month then maybe this isn't the right solution for you.",
     "expected": "escalated", "desc": "Condescending response to price concern"},
    {"msg": "Your current approach is clearly not working and you're wasting money every day you wait.",
     "expected": "escalated", "desc": "Aggressive pressure tactic"},
]

def test_handling(test):
    result = classify_objection_response(test["msg"])
    handling = result["handling"]
    passed = handling == test["expected"]
    return {
        "passed": passed,
        "details": [
            f"Response: \"{test['msg'][:70]}\"",
            f"Expected: {test['expected']}, Got: {handling} (conf: {result['confidence']:.2f})",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  TEST 3: ACTIVE LISTENING (Engine A — Semantic Similarity)
# ══════════════════════════════════════════════════════════════════

LISTENING_TESTS = [
    # === HIGH LISTENING (> 0.5) ===
    {"prospect": "We've had three certificate outages this quarter alone.",
     "rep": "Three outages in one quarter is significant. How much downtime did each one cause?",
     "expected_high": True, "desc": "Directly addressed the concern with follow-up"},
    {"prospect": "Our IT team spends 12 hours a week just tracking certificate renewals.",
     "rep": "12 hours a week on renewals is a lot of wasted time. What if that could be automated?",
     "expected_high": True, "desc": "Echoed the specific number and reframed"},
    {"prospect": "The last vendor we tried promised easy deployment but it took 4 months.",
     "rep": "I can understand the frustration with a 4-month deployment. Our average is 3 weeks, and I can show you the timeline breakdown.",
     "expected_high": True, "desc": "Referenced specific concern + offered evidence"},

    # === LOW LISTENING (< 0.4) ===
    {"prospect": "We've had three certificate outages this quarter alone.",
     "rep": "Our platform has AI-powered automation and real-time dashboards. Let me show you the demo.",
     "expected_high": False, "desc": "Ignored the concern, launched into pitch"},
    {"prospect": "I'm worried about the cost of switching vendors.",
     "rep": "We just released a new mobile app that lets you manage certificates from your phone.",
     "expected_high": False, "desc": "Completely off-topic response"},
    {"prospect": "Our budget for security tools is very limited this year.",
     "rep": "Great! Let me tell you about our Enterprise plan with unlimited certificates.",
     "expected_high": False, "desc": "Ignored budget concern, upsold"},
]

def test_listening(test):
    score = analyze_active_listening(test["prospect"], test["rep"])
    is_high = score > 0.45
    passed = is_high == test["expected_high"]
    return {
        "passed": passed,
        "details": [
            f"Prospect: \"{test['prospect'][:60]}\"",
            f"Rep: \"{test['rep'][:60]}\"",
            f"Score: {score:.3f} (expected {'> 0.45' if test['expected_high'] else '< 0.45'})",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  TEST 4: EMPATHY DETECTION (Engine B)
# ══════════════════════════════════════════════════════════════════

EMPATHY_TESTS = [
    # === HIGH EMPATHY (score > 0.6) ===
    {"prospect": "Honestly, managing certificates has been a nightmare for us.",
     "rep": "I hear you. That sounds really frustrating. What part of it causes the most headaches?",
     "expected_high": True, "desc": "Acknowledged emotion + empathetic follow-up"},
    {"prospect": "We lost a major client last month because of an expired SSL cert.",
     "rep": "That must have been devastating. Losing a client over something preventable is the worst. How has your team been handling it since?",
     "expected_high": True, "desc": "Deep empathy + open question"},
    {"prospect": "I'm under a lot of pressure from the board to fix our security posture.",
     "rep": "I understand that kind of pressure. It's not easy having the board watching. Let me show you how other companies in your position addressed this.",
     "expected_high": True, "desc": "Validated pressure + offered relatable solution"},
    {"prospect": "The last three vendors we tried all overpromised and underdelivered.",
     "rep": "I appreciate you sharing that. I totally get the skepticism. Rather than making promises, can I show you a live demo with your own data?",
     "expected_high": True, "desc": "Appreciated honesty + addressed root cause"},

    # === LOW EMPATHY (score < 0.6) ===
    {"prospect": "We lost a major client last month because of an expired SSL cert.",
     "rep": "Our platform has a 99.7% auto-renewal rate. With our Enterprise plan you get unlimited certificates.",
     "expected_high": False, "desc": "Ignored the client loss, jumped to pitching"},
    {"prospect": "I'm under a lot of pressure from the board to fix our security posture.",
     "rep": "Well, every company faces security challenges. Let me tell you about our pricing tiers.",
     "expected_high": False, "desc": "Dismissed pressure, went to pricing"},
    {"prospect": "Honestly, managing certificates has been a nightmare for us.",
     "rep": "OK. So our product does automated discovery, monitoring, and renewal. Want to see a demo?",
     "expected_high": False, "desc": "Minimal acknowledgment, straight to features"},
    {"prospect": "The last three vendors we tried all overpromised and underdelivered.",
     "rep": "We're different from other vendors. Our technology is industry-leading and award-winning.",
     "expected_high": False, "desc": "Generic claim, no empathy for bad experience"},
]

def test_empathy(test):
    result = detect_empathy(test["prospect"], test["rep"])
    score = result["empathy_score"]
    passed = (score > 0.6) == test["expected_high"]
    return {
        "passed": passed,
        "details": [
            f"Prospect: \"{test['prospect'][:60]}\"",
            f"Rep: \"{test['rep'][:60]}\"",
            f"Score: {score:.2f} | Showed: {result['rep_showed_empathy']} | P_emo: {result['prospect_emotion']} | R_emo: {result['rep_dominant_emotion']}",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  TEST 5: PRESSURE LEVEL (Engine B)
# ══════════════════════════════════════════════════════════════════

PRESSURE_TESTS = [
    # === CONSULTATIVE ===
    {"msg": "I appreciate you sharing that. What would an ideal solution look like for your team?",
     "expected": "consultative", "desc": "Gentle, exploratory question"},
    {"msg": "That makes sense. Would it help if I put together a comparison document for your team to review?",
     "expected": "consultative", "desc": "Helpful, no pressure"},
    {"msg": "Take your time thinking it over. I'm happy to answer any questions whenever you're ready.",
     "expected": "consultative", "desc": "Patient, no urgency"},

    # === URGENT ===
    {"msg": "I should mention that this pricing is only valid until the end of the month.",
     "expected": "urgent", "desc": "Time-limited offer"},

    # === DEMANDING ===
    {"msg": "You're losing money every single day you don't have this in place. How much longer can you afford to wait?",
     "expected": "demanding", "desc": "Fear-based pressure"},
    {"msg": "If you can't see the value in this then frankly I'm not sure what more I can show you.",
     "expected": "demanding", "desc": "Condescending frustration"},
]

def test_pressure(test):
    result = classify_pressure_level(test["msg"])
    level = result["pressure_level"]
    passed = level == test["expected"]
    return {
        "passed": passed,
        "details": [
            f"Message: \"{test['msg'][:70]}\"",
            f"Expected: {test['expected']}, Got: {level} (score: {result['pressure_score']:.2f})",
        ],
    }


# ══════════════════════════════════════════════════════════════════
#  TEST 6: FULL PIPELINE (Engine A + B combined)
# ══════════════════════════════════════════════════════════════════

PIPELINE_TESTS = [
    {"prospect": "That pricing is way too high for what we'd get.",
     "rep": "I understand your concern about the pricing. What budget range would work for your team? We have several tiers that might fit.",
     "desc": "Objection + empathetic handling + exploration",
     "expect_objection": True, "expect_handling": "resolved", "expect_empathy_high": True},

    {"prospect": "Tell me more about your integration capabilities.",
     "rep": "We integrate natively with AWS, Azure, Kubernetes, and Terraform. Want me to walk through how it works with your stack?",
     "desc": "Question (not objection) + relevant response",
     "expect_objection": False, "expect_handling": None, "expect_empathy_high": True},

    {"prospect": "I'm not sure this is the right time for us. We have a lot going on.",
     "rep": "Our product has 15 features that your competitors don't have. Let me list them all for you.",
     "desc": "Timing objection + ignored concern + feature dump",
     "expect_objection": True, "expect_handling": "deflected", "expect_empathy_high": False},
]

def test_pipeline(test):
    intent = run_intent_analysis(test["prospect"], test["rep"])
    emotion = run_emotion_analysis(test["prospect"], test["rep"])

    checks = []
    all_passed = True

    # Check objection detection
    obj_pass = intent["is_objection"] == test["expect_objection"]
    checks.append(f"Objection: expected={test['expect_objection']}, got={intent['is_objection']} (conf: {intent['objection_confidence']:.2f}) {'OK' if obj_pass else 'FAIL'}")
    all_passed = all_passed and obj_pass

    # Check handling (only if objection expected)
    if test["expect_handling"]:
        h = intent.get("objection_handling")
        h_pass = h == test["expect_handling"]
        checks.append(f"Handling: expected={test['expect_handling']}, got={h} {'OK' if h_pass else 'FAIL'}")
        all_passed = all_passed and h_pass

    # Check empathy
    emp_score = emotion["empathy"]["empathy_score"]
    emp_pass = (emp_score > 0.6) == test["expect_empathy_high"]
    checks.append(f"Empathy: score={emp_score:.2f}, expected {'high' if test['expect_empathy_high'] else 'low'} {'OK' if emp_pass else 'FAIL'}")
    all_passed = all_passed and emp_pass

    # Listening
    checks.append(f"Listening: {intent['active_listening_score']:.2f}")
    checks.append(f"Pressure: {emotion['pressure']['pressure_level']} ({emotion['pressure']['pressure_score']:.2f})")

    return {"passed": all_passed, "details": checks}


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print(f"\n{BOLD}{'=' * 80}")
    print(f"  SALESFORGE AI — ENGINE A + ENGINE B COMPREHENSIVE TEST SUITE")
    print(f"{'=' * 80}{RESET}")

    results = []

    results.append(run_test("TEST 1: OBJECTION DETECTION (Engine A — DeBERTa NLI)", OBJECTION_TESTS, test_objection))
    results.append(run_test("TEST 2: OBJECTION HANDLING CLASSIFICATION (Engine A)", HANDLING_TESTS, test_handling))
    results.append(run_test("TEST 3: ACTIVE LISTENING (Engine A — Semantic Similarity)", LISTENING_TESTS, test_listening))
    results.append(run_test("TEST 4: EMPATHY DETECTION (Engine B — Emotion-RoBERTa)", EMPATHY_TESTS, test_empathy))
    results.append(run_test("TEST 5: PRESSURE LEVEL (Engine B — GoEmotions)", PRESSURE_TESTS, test_pressure))
    results.append(run_test("TEST 6: FULL PIPELINE (Engine A + B Combined)", PIPELINE_TESTS, test_pipeline))

    total_correct = sum(r[0] for r in results)
    total_tests = sum(r[1] for r in results)

    print(f"\n{BOLD}{'=' * 80}")
    print(f"  OVERALL: {total_correct}/{total_tests} = {total_correct/total_tests*100:.0f}%")
    print(f"{'=' * 80}{RESET}\n")


if __name__ == "__main__":
    main()
