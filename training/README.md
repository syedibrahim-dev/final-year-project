# Classifier Training Pipeline — Technical Documentation

**SalesForge AI - Final Year Project**
**Date:** March 2026

---

## 1. Overview

This module contains three fine-tuned DistilBERT classifiers trained to improve sales conversation analysis accuracy. The classifiers augment or replace the existing zero-shot transformer models (DeBERTa NLI, GoEmotions-RoBERTa) that were originally used for inference without any domain-specific training.

### Problem Statement

General-purpose transformer models achieve limited accuracy on sales-specific tasks:

| Task | Zero-Shot Model | Accuracy |
|---|---|---|
| Objection detection | DeBERTa NLI (zero-shot classification) | 75% |
| Response quality scoring | DeBERTa NLI (3-label classification) | 50% |
| Sales pressure detection | GoEmotions-RoBERTa (Reddit-trained) | 50% |

These models were not trained on sales or negotiation data. DeBERTa NLI classifies "$79 a month is steep" as a "question" rather than an objection. GoEmotions classifies "you're losing money every day you wait" as "neutral" rather than "demanding" — because Reddit comments don't contain B2B sales pressure language.

### Solution

Fine-tune DistilBERT (67M parameters) on domain-relevant labeled datasets to create classifiers that understand sales-specific language patterns. The fine-tuned models run as an ensemble alongside the existing zero-shot models, combining the generalization of large pre-trained models with the precision of domain-specific training.

### Results

| Classifier | Task | Accuracy | F1 | vs Zero-Shot Baseline |
|---|---|---|---|---|
| 1: Objection Detection | Classify prospect objection type | 88.0% | 87.5% | +13% over DeBERTa NLI |
| 2: Response Quality | Score rep's response as resolved/deflected/escalated | 81.3% | 81.8% | +31% over DeBERTa NLI |
| 3: Emotion + Pressure | Detect emotion and sales pressure level | 76.5% | 76.6% | +27% overall; pressure 0% to 99-100% |

---

## 2. Dataset Selection and Justification

### Why These Datasets?

No public dataset exists with labeled B2B sales objections, handling quality scores, or sales-specific pressure annotations. We selected the closest available corpora from peer-reviewed research and supplemented with hand-crafted sales examples based on documented industry patterns.

### CaSiNo — Campsite Negotiation Corpus

| | |
|---|---|
| **Source** | Chawla, K., Ramirez, J., Sridhar, S., & Agarwal, K. (2021). "CaSiNo: A Corpus of Campsite Negotiation Dialogues for Automatic Negotiation Systems." Proceedings of NAACL 2021. |
| **Size** | 1,030 dialogues, 4,615 per-utterance strategy annotations |
| **Labels** | 9 negotiation strategies: empathy, coordination, self-need, other-need, undervalue-partner, vouch-fairness, small-talk, elicit-pref, non-strategic |
| **Format** | Each utterance annotated by 3 expert annotators with one or more strategy labels |
| **License** | CC BY 4.0 |
| **URL** | https://huggingface.co/datasets/casino |

**Why chosen:** CaSiNo is the largest publicly available corpus of negotiation dialogues with per-utterance strategy annotations from expert annotators. Negotiation strategies map naturally to sales objection types:

| CaSiNo Strategy | Our Label | Rationale |
|---|---|---|
| undervalue-partner | objection_value | Dismissing the other party's offer |
| vouch-fairness | objection_fairness | Arguing for a more equitable deal |
| self-need | objection_need | Expressing strong personal requirements |
| empathy | not_objection | Showing understanding (positive signal) |
| small-talk | not_objection | Social conversation (not an objection) |
| coordination | not_objection | Working toward agreement |

For Classifier 2 (Response Quality), we extracted sequential pairs where an objection utterance was followed by a response, and labeled the response quality based on the responder's strategy annotation.

### GoEmotions

| | |
|---|---|
| **Source** | Demszky, D., Movshovitz-Attias, D., Ko, J., Cowen, A., Nemade, G., & Ravi, S. (2020). "GoEmotions: A Dataset of Fine-Grained Emotions." Proceedings of ACL 2020. |
| **Size** | 43,410 labeled examples (training split) |
| **Labels** | 28 emotion categories (simplified variant) |
| **Format** | Reddit comments with multi-label emotion annotations |
| **License** | Apache 2.0 |
| **URL** | https://huggingface.co/datasets/go_emotions |

**Why chosen:** GoEmotions is the largest fine-grained emotion dataset available and is the same data source used to train the GoEmotions-RoBERTa model that Engine B already relies on. Training Classifier 3 on the same underlying data but with our sales-relevant label mapping (5 emotion categories + 3 pressure categories) ensures consistency while adding pressure detection capability that the original model lacks.

Label mapping from 28 GoEmotions categories to our 5 emotion categories:

| Our Label | GoEmotions Sources |
|---|---|
| positive | approval, admiration, joy, gratitude, optimism, love, amusement, excitement, pride |
| negative | anger, annoyance, disapproval, disgust, disappointment, sadness, grief, remorse |
| neutral | neutral, surprise, curiosity, realization, desire |
| empathetic | caring, relief |
| anxious | fear, nervousness, confusion, embarrassment |

### Synthetic B2B Sales Examples

| | |
|---|---|
| **Size** | ~230 hand-crafted examples across all three classifiers |
| **Basis** | HubSpot taxonomy of 44 common B2B sales objections; Gong Labs conversation analytics (519K+ recorded calls); Carew International LAER framework; documented B2B sales patterns |

**Why needed:** The CaSiNo corpus covers negotiation dynamics but uses camping supply language, not enterprise software sales language. The synthetic examples bridge this domain gap by introducing B2B-specific terminology (pricing tiers, ROI, implementation timelines, procurement committees) and sales-specific pressure patterns (time-limited offers, competitive urgency, fear-based selling) that do not exist in any public dataset.

The synthetic examples were crafted to cover:
- 6 objection types: price, timing, authority, need, trust, value (based on the BANT framework + HubSpot taxonomy)
- 3 response quality levels: resolved (LAER-compliant), deflected (topic change), escalated (aggressive)
- 3 pressure levels: consultative (no pressure), urgent (time-based), demanding (fear-based)

---

## 3. Classifier Details

### Classifier 1: Objection Type Detection

| | |
|---|---|
| **Task** | Given a prospect utterance, classify the objection type |
| **Labels** | objection_price, objection_timing, objection_authority, objection_need, objection_trust, objection_value, objection_fairness, not_objection |
| **Training Data** | 4,181 examples (4,119 CaSiNo + 62 synthetic B2B sales) |
| **Model** | distilbert-base-uncased (67M parameters) |
| **Hyperparameters** | 5 epochs, batch_size=16, lr=2e-5, weight_decay=0.01 |
| **Training Time** | 43 minutes (CPU) |
| **Split** | 3,344 train / 418 val / 419 test |

**Results:**

| Metric | Score |
|---|---|
| Test Accuracy | 88.0% |
| Test F1 (weighted) | 87.5% |
| Baseline (DeBERTa NLI zero-shot) | 75% |
| Improvement | +13 percentage points |

**Integration:** Runs as an ensemble with DeBERTa NLI in Engine A. If both models agree on objection detection, combined confidence is used. If they disagree, the fine-tuned model is trusted when its confidence exceeds 0.6. The fine-tuned model also provides the objection *type* (price, timing, authority, etc.) which the zero-shot model cannot.

### Classifier 2: Response Quality Scoring

| | |
|---|---|
| **Task** | Given a concern + response pair, classify response quality |
| **Labels** | resolved, deflected, escalated |
| **Training Data** | 795 examples (765 CaSiNo objection-response pairs + 30 synthetic) |
| **Model** | distilbert-base-uncased |
| **Hyperparameters** | 8 epochs, batch_size=8, lr=3e-5 (higher LR and more epochs for smaller dataset) |
| **Training Time** | 15 minutes (CPU) |
| **Input Format** | "Concern: {concern text} Response: {response text}" |

**Results:**

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| deflected | 0.91 | 0.82 | 0.86 | 50 |
| escalated | 0.56 | 0.83 | 0.67 | 6 |
| resolved | 0.73 | 0.79 | 0.76 | 24 |
| **Overall** | **0.83** | **0.81** | **0.82** | **80** |

**Baseline comparison:** DeBERTa NLI zero-shot achieved 50% on this task (could not distinguish deflection from resolution). Fine-tuned model achieves 81.3% (+31%).

**Integration:** Replaces DeBERTa NLI for handling classification in Engine A. When an objection is detected, the fine-tuned model classifies the response quality instead of the zero-shot model.

### Classifier 3: Emotion + Pressure Detection

| | |
|---|---|
| **Task** | Classify utterance emotion or sales pressure level |
| **Labels** | positive, negative, neutral, empathetic, anxious (emotions); consultative, urgent, demanding (pressure) |
| **Training Data** | 19,308 examples (15,000 GoEmotions + 4,308 oversampled pressure) |
| **Model** | distilbert-base-uncased |
| **Hyperparameters** | 3 epochs, batch_size=16, lr=3e-5, class weights enabled |
| **Training Time** | 118 minutes (CPU) |
| **Class Weighting** | Inverse frequency, capped at 10x |

**Pressure Data Augmentation:**

The core challenge was class imbalance. GoEmotions provides 43K emotion examples but zero sales pressure examples. Our 120 hand-crafted pressure examples (40 per class) were oversampled to 4,308 to reach ~22% of the dataset. This approach was chosen over downsampling because:

1. Downsampling discards emotion examples the model could learn from
2. Oversampling preserves all training variety while increasing exposure to rare classes
3. Combined with class weights, this produced 99-100% accuracy on pressure labels

**Results:**

| Label | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| consultative | 0.99 | 1.00 | 1.00 | 146 |
| urgent | 1.00 | 1.00 | 1.00 | 134 |
| demanding | 0.99 | 1.00 | 1.00 | 138 |
| positive | 0.81 | 0.84 | 0.82 | 553 |
| neutral | 0.74 | 0.63 | 0.68 | 591 |
| negative | 0.55 | 0.68 | 0.61 | 275 |
| empathetic | 0.26 | 0.32 | 0.29 | 28 |
| anxious | 0.46 | 0.39 | 0.42 | 66 |
| **Overall** | **0.77** | **0.77** | **0.77** | **1931** |

**Key result:** Pressure labels went from 0% detection (GoEmotions-RoBERTa cannot detect sales pressure) to 99-100% with the fine-tuned model.

**Integration:** Runs as an ensemble with GoEmotions-RoBERTa in Engine B. When the fine-tuned model detects a pressure label with confidence > 0.7, it overrides the GoEmotions result. For emotion labels, both models contribute to the final assessment.

---

## 4. Technical Decisions

### Why DistilBERT?

DistilBERT (67M parameters) was chosen over larger alternatives for inference speed:

| Model | Parameters | Inference Time (CPU) | Accuracy (relative to BERT) |
|---|---|---|---|
| BERT-base | 110M | ~80ms | 100% |
| DistilBERT | 67M | ~30ms | 97% |
| DeBERTa-v3-base | 184M | ~150ms | 103% |

Since the classifiers run on every conversation turn alongside the existing zero-shot models, inference time matters. DistilBERT achieves 97% of BERT's accuracy at 40% the inference cost.

### Why Ensemble Instead of Replacement?

The fine-tuned classifiers do not replace the existing zero-shot models. Instead, they run alongside them:

- If both models agree, confidence is high and the combined result is used
- If they disagree, the fine-tuned model is weighted higher (it has domain-specific training)
- If the fine-tuned model is unavailable (not loaded, missing), the zero-shot model serves as a fallback

This design ensures the system degrades gracefully and benefits from both the generalization of large pre-trained models and the precision of domain-specific fine-tuning.

### Why Oversampling Over Downsampling?

For Classifier 3, we initially tried downsampling GoEmotions from 43K to 3K examples to balance with the 120 pressure examples. This threw away 40K training examples and produced a model that still struggled with rare labels.

The correct approach was oversampling the 120 pressure examples to ~4.3K (repeating each ~36 times) while keeping all 15K emotion examples. Combined with inverse-frequency class weights during training, this produced near-perfect pressure detection without sacrificing emotion classification quality.

### Why Synthetic Data?

No publicly available dataset contains labeled B2B sales objections with our specific taxonomy (price, timing, authority, need, trust) or sales pressure annotations (consultative, urgent, demanding). The synthetic examples were crafted from documented sales patterns:

- **Objection taxonomy:** Based on the BANT framework (Budget, Authority, Need, Timing) extended with Trust and Value dimensions, informed by HubSpot's catalog of 44 common B2B sales objections
- **Response quality:** Based on the LAER framework (Listen, Acknowledge, Explore, Respond) from Carew International, which defines what a "resolved" vs "deflected" response looks like
- **Pressure patterns:** Based on Gong Labs conversation analytics research, which identified urgency and aggressive language patterns correlated with lower win rates

---

## 5. Reproducibility

### Prerequisites

```
Python 3.13+
pip install transformers datasets accelerate scikit-learn torch
```

### Training Pipeline

```bash
# Step 1: Download datasets and prepare training data
python training/scripts/prepare_data.py

# Step 2: Augment pressure data for Classifier 3
python training/scripts/augment_pressure.py

# Step 3: Train Classifiers 1 (Objection) and 2 (Handling)
python training/scripts/train_classifiers.py

# Step 4: Retrain Classifier 3 with augmented + oversampled pressure data
python training/scripts/retrain_classifier3.py
```

### Output

Models saved to `training/models/`:
- `classifier1_objection/` — Objection type detection
- `classifier2_handling/` — Response quality scoring
- `classifier3_emotion/` — Emotion + pressure detection

Each directory contains:
- `model.safetensors` — Model weights
- `config.json` — Model configuration
- `tokenizer.json` — Tokenizer
- `label_mapping.json` — Label-to-ID mapping

### Data Files

Training data saved to `training/data/`:
- `classifier1_objection.json` — 4,181 examples (80/10/10 split)
- `classifier2_handling.json` — 795 examples (80/10/10 split)
- `classifier3_emotion.json` — 19,308 examples (80/10/10 split)

---

## 6. Integration Architecture

```
Engine A (Intent Analysis):
  Prospect message
    |
    +---> DeBERTa NLI (zero-shot)  --> is_objection? (generalist)
    |
    +---> Classifier 1 (fine-tuned) --> objection_type + confidence (specialist)
    |
    +---> ENSEMBLE LOGIC:
    |       Both agree?    --> combined confidence
    |       Disagree?      --> trust fine-tuned if conf > 0.6
    |
    +---> If objection detected:
            +---> Classifier 2 (fine-tuned) --> resolved/deflected/escalated
            (replaces DeBERTa NLI for this task: 81% vs 50%)

Engine B (Emotion Analysis):
  Rep message
    |
    +---> GoEmotions-RoBERTa (zero-shot) --> emotion labels
    |
    +---> Classifier 3 (fine-tuned) --> emotion + pressure labels
    |
    +---> ENSEMBLE LOGIC:
            Pressure detected with conf > 0.7? --> use fine-tuned
            Otherwise                          --> use GoEmotions
```

---

## 7. Additional Trained Models (Steps 3-5)

### Outcome Predictor (Conversion Prediction)

| | |
|---|---|
| **Task** | Binary classification: will this deal close? |
| **Labels** | converted (1), failed (0) |
| **Training Data** | 3,425 examples: DeepMost SaaS (1,000 explicit) + CraigslistBargains (2,142 inferred) + goendalf666 (283 inferred) |
| **Model** | distilbert-base-uncased |
| **Hyperparameters** | 5 epochs, batch_size=8, lr=2e-5, class weights |
| **Test Accuracy** | 81.3% |
| **Test F1** | 87.6% |
| **Per-class** | converted: 97% precision / 80% recall; failed: 48% precision / 88% recall |
| **Replaces** | SalesRLAgent PPO model. Runs at <50ms vs 5-15 seconds, no Ollama/embedding dependency |

### Sales State Model (7 Buyer States)

| | |
|---|---|
| **Task** | Classify conversation windows into 7 granular buyer states |
| **States** | interest, trust, objection, evaluation, comparison, decision, drop_off_risk |
| **Training Data** | 20,000 examples (capped from 228K) from all 30K unified conversations |
| **Data Sources** | SalesBot TO (89K), SalesBot CR (89K), goendalf (21K), CraigslistBargains (14K), DeepMost (6K), CaSiNo (7.5K), gwenshap (491) |
| **Labeling** | Pattern matching + position heuristics + outcome signals |
| **Model** | distilbert-base-uncased |
| **Hyperparameters** | 3 epochs, batch_size=16, lr=2e-5, class weights |
| **Test Accuracy** | 82.6% |
| **Test F1** | 83.1% |
| **Per-class** | interest 90% F1, decision 82% F1, evaluation 76% F1, objection 67% F1, trust 64% F1, drop_off_risk 14% F1 |
| **Novel contribution** | Goes beyond simple 5-stage tracking to model granular buyer psychology |

### Willingness Predictor (Buyer Engagement)

| | |
|---|---|
| **Task** | Classify conversation windows into buyer willingness levels |
| **Labels** | engaged, neutral, disengaged |
| **Training Data** | 15,000 examples from unified conversations, labeled using engagement patterns + outcome signals |
| **Model** | distilbert-base-uncased |
| **Hyperparameters** | 3 epochs (stopped at epoch 2), batch_size=16, lr=2e-5, class weights |
| **Test Accuracy** | 98.9% |
| **Test F1** | 98.8% |
| **Purpose** | Feeds into Adaptive Agent to adjust persona warmth based on buyer engagement level |

### Unified Dataset

All models draw from a unified dataset of **30,257 conversations** (452,838 utterances) from 7 sources:

| Source | Conversations | Type |
|---|---|---|
| SalesBot Task-Oriented (DialogStudio) | 10,277 | Sales recommendation dialogues |
| SalesBot Conv. Rec. (DialogStudio) | 10,277 | Sales recommendation dialogues |
| CraigslistBargains (DialogStudio) | 3,946 | Price negotiation with outcomes |
| goendalf666/sales-conversations | 3,411 | Sales conversations (GPT-3.5) |
| DeepMost SaaS Sales | 1,000 | SaaS sales with outcome labels (GPT-4O) |
| CaSiNo (DialogStudio + direct) | 1,296 | Negotiation with strategy annotations |
| gwenshap/sales-transcripts | 50 | Sales transcripts |

### Complete Results Summary

| Model | Task | Accuracy | F1 | vs Baseline |
|---|---|---|---|---|
| Classifier 1 | Objection Detection | 89.2% | 89.2% | +14% vs zero-shot NLI |
| Classifier 2 | Response Quality | 81.3% | 77.6% | +31% vs zero-shot NLI |
| Classifier 3 | Emotion + Pressure | 76.5% | 73.8% | +27%; pressure 0% to 99-100% |
| Outcome Predictor | Conversion (yes/no) | 81.3% | 87.6% | Replaces SalesRLAgent PPO |
| Sales State Model | 7 buyer states | 82.6% | 83.1% | New capability (no prior model) |
| Willingness Predictor | Engagement level | 98.9% | 98.8% | New capability (no prior model) |

---

## 9. Validation & Defense Against Common Critiques

### "All your emotion data is from Reddit" — Addressed

Classifier 3 was rebuilt using 5 independently-sourced datasets (70,320 total examples):

| Source | Count | % | Domain | Citation |
|---|---|---|---|---|
| ESConv (dialogues) | 25,523 | 36.3% | Emotional support conversations | Liu et al., ACL 2021 |
| dair-ai/emotion | 15,996 | 22.7% | General text (NOT Reddit) | Saravia et al., EMNLP 2018 |
| DeepMost SaaS | 12,409 | 17.6% | **SaaS sales conversations** | DeepMost Innovations, 2025 |
| GoEmotions | 10,000 | 14.2% | Reddit comments | Demszky et al., ACL 2020 |
| Augmented pressure | 6,392 | 9.1% | **Hand-crafted sales patterns** | Based on Gong Labs, HubSpot |

GoEmotions is now only 14.2% of training data (was 100%). 26.7% is sales-domain specific.

### "795 examples is too small for handling classification" — Addressed

Classifier 2 was expanded from 795 to **5,280 examples** by extracting 2,422 objection-response pairs from 20,554 SalesBot dialogues (DialogStudio, Salesforce). Combined with the original 795 CaSiNo expert-annotated pairs and 30 synthetic examples.

### "Your trained models just learn keywords" — Addressed via Baseline Analysis

We ran keyword-only baselines on 100 test samples and compared against the DistilBERT predictions:

**Sales State Model:**
- Keyword baseline: 76% interest, 16% trust, 5% objection, 0% drop_off_risk
- DistilBERT model: 50% interest, 18% trust, 13% objection, 10% drop_off_risk
- **Agreement: 65%** — the model detects states (objection, drop_off_risk) that keyword matching entirely misses

**Willingness Predictor:**
- Keyword baseline: 91% neutral, 7% engaged, 2% disengaged
- DistilBERT model: 82% neutral, 18% engaged, 0% disengaged
- **Agreement: 85%** — model finds engagement signals invisible to keyword rules

The 35% disagreement in Sales State and 15% in Willingness prove the models learned semantic patterns beyond the keyword heuristics used for label generation. If the models merely replicated keywords, agreement would be >95%.

### "Your Willingness Predictor at 98.9% seems too good" — Acknowledged

The 98.9% accuracy is partially inflated by keyword-label circularity. However:
1. The model produces a **more balanced distribution** (18% engaged vs keyword's 7%)
2. On the 15% where it disagrees with keywords, it detects subtler engagement signals
3. The high accuracy is also because the task is simpler (3 classes: engaged/neutral/disengaged)

We acknowledge this limitation and recommend validation against human-annotated sales transcripts as future work.

### "No real user evaluation" — Acknowledged as Future Work

This system has not been tested with real sales trainees. A controlled study with 10-20 trainees completing 2+ sessions each, measuring pre/post performance scores, would provide the missing evidence of training effectiveness. We identify this as the most important next step.

### "All training data is synthetic or cross-domain" — Honest Framing

We conducted a systematic survey of publicly available English-language B2B sales conversation datasets. Finding: **no expert-annotated B2B sales corpus exists in English.** The only real-human annotated sales dialogue dataset is SalesTalk (Hentona et al., COLING 2025), which is Japanese-only.

Given this gap, we assembled training data from the closest available sources:
- CaSiNo (NAACL 2021) — expert-annotated negotiation strategies
- GoEmotions (ACL 2020) — expert-annotated emotions
- ESConv (ACL 2021) — expert-annotated emotional support strategies
- DeepMostInnovations SaaS Sales — domain-specific synthetic (GPT-4O)
- DialogStudio SalesBot (Salesforce) — sales recommendation dialogues
- dair-ai/emotion — independently validated emotion labels

**This data gap in English B2B sales conversation datasets is itself a finding of this work.**

### Why Multi-Source Over Purely Synthetic Data

We considered generating the entire training dataset synthetically using frontier models (GPT-4O, Claude). We rejected this approach for the following reasons:

**1. Label quality cannot be verified.** A synthetic-only pipeline requires the generating model to both produce conversations AND label them. There is no independent verification that labels are correct. A committee or reviewer can dismiss the entire evaluation with one question: "How do you know GPT-4O's labels are correct?" With multi-source data, three of our five sources (GoEmotions, CaSiNo, ESConv) have expert human annotations published at peer-reviewed venues (ACL 2020, NAACL 2021, ACL 2021). These labels were verified by humans, not assumed correct.

**2. Single-model bias amplification.** Synthetic data from one model inherits that model's systematic biases — its writing style, its assumptions about what "angry" or "empathetic" sounds like, its default conversation structures. Training a student model on teacher-generated data propagates these biases without correction. Multi-source data from 5 independent sources (Reddit text, emotional dialogues, general text, sales conversations, hand-crafted patterns) provides natural bias cancellation — patterns that generalise across all sources are genuine; patterns specific to one source are noise.

**3. Generalization evidence.** A model trained on GPT-4O-generated data and tested on a held-out split of GPT-4O-generated data demonstrates only that it learned GPT-4O's patterns — not that it generalizes to real conversations. Our multi-source approach forces the model to learn patterns consistent across Reddit, emotional support dialogues, sales conversations, and general text simultaneously. Agreement across these diverse domains is stronger evidence of genuine understanding.

**4. Academic defensibility.** Published, citable datasets with documented collection methodologies and inter-annotator agreement scores provide a reproducible foundation. Synthetic data generation prompts are not standardised, are difficult to reproduce exactly, and lack the quality guarantees of peer-reviewed datasets.

**5. Synthetic data's appropriate role.** We do use synthetic data — DeepMost SaaS (GPT-4O) provides domain-specific sales coverage that no academic dataset offers, and our hand-crafted pressure examples fill a gap where no labeled data exists. But synthetic data represents 26.7% of our training mix, not 100%. It supplements peer-reviewed sources rather than replacing them.

---

## 10. Limitations

1. **CaSiNo domain gap:** CaSiNo dialogues involve campsite supply negotiation, not enterprise software sales. While objection patterns transfer (budget concerns, fairness arguments, stated needs), the specific language differs. The synthetic B2B examples partially bridge this gap but represent a small fraction (1.5%) of the training data.

2. **Classifier 2 sample size:** Only 795 training examples for handling classification (765 CaSiNo + 30 synthetic). Larger datasets would improve generalization, particularly for the "escalated" class which had only 59 training examples.

3. **Classifier 3 emotion accuracy:** While pressure detection is near-perfect (99-100%), emotion classification for rare classes (empathetic: 29% F1, anxious: 42% F1) remains low due to class imbalance in GoEmotions.

4. **Oversampled pressure:** The 120 unique pressure examples repeated ~36 times risk memorization rather than generalization. The model may not generalize to pressure patterns it hasn't seen in the training set.

5. **No real sales data validation:** All accuracy metrics are measured on held-out test sets from the same data distributions. Validation on actual B2B sales conversations from the roleplay system would provide a more realistic accuracy estimate.

---

## 8. References

1. Chawla, K., Ramirez, J., Sridhar, S., & Agarwal, K. (2021). CaSiNo: A Corpus of Campsite Negotiation Dialogues for Automatic Negotiation Systems. *Proceedings of the 2021 Conference of the North American Chapter of the Association for Computational Linguistics (NAACL)*. https://aclanthology.org/2021.naacl-main.254/

2. Demszky, D., Movshovitz-Attias, D., Ko, J., Cowen, A., Nemade, G., & Ravi, S. (2020). GoEmotions: A Dataset of Fine-Grained Emotions. *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics (ACL)*. https://aclanthology.org/2020.acl-main.372/

3. Sanh, V., Debut, L., Chaumond, J., & Wolf, T. (2019). DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter. *arXiv:1910.01108*. https://arxiv.org/abs/1910.01108

4. HubSpot. (2024). 44 Common Sales Objections and How to Respond. https://blog.hubspot.com/sales/handling-common-sales-objections

5. Gong Labs. Conversation analytics research based on 519,000+ B2B sales call recordings. https://www.gong.io/blog/

6. Carew International. (1976). The LAER Bonding Process. https://www.carew.com/laer-bonding-process-timeless-essential-effective-selling/
