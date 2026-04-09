"""
Generate training visualization plots for all classifiers.
Produces loss curves, accuracy curves, and confusion matrices.
"""
import sys, os, json
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "plots")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_trainer_state(name):
    """Find and load trainer_state.json from model checkpoints."""
    model_dir = os.path.join(MODEL_DIR, name)
    state_file = None
    # Check checkpoints first, then root
    for root, dirs, files in os.walk(model_dir):
        if "trainer_state.json" in files:
            state_file = os.path.join(root, "trainer_state.json")

    if not state_file:
        return None

    with open(state_file, "r") as f:
        return json.load(f)


def extract_metrics(state):
    """Extract train loss and eval metrics from trainer state."""
    log_history = state.get("log_history", [])

    train_data = []
    eval_data = []

    for entry in log_history:
        if "loss" in entry and "eval_loss" not in entry:
            train_data.append({"epoch": entry.get("epoch", 0), "loss": entry["loss"]})
        if "eval_accuracy" in entry:
            eval_data.append({
                "epoch": entry.get("epoch", 0),
                "eval_loss": entry.get("eval_loss", 0),
                "accuracy": entry["eval_accuracy"],
                "f1": entry.get("eval_f1", 0),
            })

    return train_data, eval_data


def plot_classifier(name, title, train_data, eval_data, output_path):
    """Generate a 2x1 subplot: loss curve + accuracy/F1 curve."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)

    # ── Loss curve ──
    ax1 = axes[0]
    train_epochs = [d["epoch"] for d in train_data]
    train_losses = [d["loss"] for d in train_data]
    eval_epochs = [d["epoch"] for d in eval_data]
    eval_losses = [d["eval_loss"] for d in eval_data]

    ax1.plot(train_epochs, train_losses, "b-o", markersize=3, label="Train Loss", alpha=0.7)
    ax1.plot(eval_epochs, eval_losses, "r-s", markersize=6, label="Val Loss", linewidth=2)
    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training & Validation Loss")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # ── Accuracy + F1 curve ──
    ax2 = axes[1]
    accuracies = [d["accuracy"] * 100 for d in eval_data]
    f1s = [d["f1"] * 100 for d in eval_data]

    ax2.plot(eval_epochs, accuracies, "g-o", markersize=8, linewidth=2, label="Accuracy")
    ax2.plot(eval_epochs, f1s, "m-s", markersize=8, linewidth=2, label="F1 Score")

    # Annotate final values
    if accuracies:
        ax2.annotate(f"{accuracies[-1]:.1f}%",
                     xy=(eval_epochs[-1], accuracies[-1]),
                     xytext=(10, 10), textcoords="offset points",
                     fontsize=11, fontweight="bold", color="green")
    if f1s:
        ax2.annotate(f"{f1s[-1]:.1f}%",
                     xy=(eval_epochs[-1], f1s[-1]),
                     xytext=(10, -15), textcoords="offset points",
                     fontsize=11, fontweight="bold", color="purple")

    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Score (%)")
    ax2.set_title("Validation Accuracy & F1")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 100])

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {output_path}")


def plot_comparison_bar(output_path):
    """Generate a comparison bar chart: all 6 models."""
    models = ["Objection\nDetection", "Response\nQuality", "Emotion +\nPressure",
              "Outcome\nPredictor", "Sales\nState", "Willingness\nPredictor"]

    before = [75.0, 50.0, 50.0, 40.0, 0, 0]  # zero-shot / no model baselines
    after = [89.2, 81.3, 76.5, 81.3, 82.6, 98.9]  # final trained models

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(14, 6))

    bars1 = ax.bar(x - width/2, before, width, label="Before (Zero-Shot / No Model)", color="#ef4444", alpha=0.8)
    bars2 = ax.bar(x + width/2, after, width, label="After (Fine-Tuned DistilBERT)", color="#10b981", alpha=0.8)

    # Value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f"{height:.1f}%",
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points",
                            ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_ylabel("Accuracy (%)")
    ax.set_title("All 6 Trained Models: Before vs After", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim([0, 110])
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {output_path}")


def plot_dataset_composition(output_path):
    """Pie charts showing unified dataset sources."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Training Data Sources", fontsize=13, fontweight="bold")

    # Unified dataset sources
    sources = {
        "SalesBot TO\n(10,277)": 10277,
        "SalesBot CR\n(10,277)": 10277,
        "CraigslistBargains\n(3,946)": 3946,
        "goendalf666\n(3,411)": 3411,
        "DeepMost SaaS\n(1,000)": 1000,
        "CaSiNo\n(1,296)": 1296,
        "gwenshap\n(50)": 50,
    }
    colors = ["#3b82f6", "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b"]
    axes[0].pie(sources.values(), labels=sources.keys(), autopct="%1.0f%%",
                colors=colors, startangle=90, textprops={"fontsize": 8})
    axes[0].set_title("Unified Dataset\n(30,257 conversations)")

    # Model accuracy comparison
    models = ["C1\nObjection", "C2\nHandling", "C3\nEmotion", "Outcome", "State", "Willing."]
    accuracies = [89.2, 81.3, 76.5, 81.3, 82.6, 98.9]
    bar_colors = ["#10b981" if a >= 80 else "#f59e0b" if a >= 70 else "#ef4444" for a in accuracies]
    bars = axes[1].bar(models, accuracies, color=bar_colors, alpha=0.85)
    for bar, acc in zip(bars, accuracies):
        axes[1].annotate(f"{acc:.1f}%", xy=(bar.get_x() + bar.get_width()/2, acc),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=10, fontweight="bold")
    axes[1].set_ylim([0, 110])
    axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_title("All 6 Models — Test Accuracy")
    axes[1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved: {output_path}")


def main():
    print("Generating Training Visualizations\n")

    # Individual classifier training curves
    for name, title in [
        ("classifier1_objection", "Classifier 1: Objection Detection (DistilBERT)"),
        ("classifier2_handling", "Classifier 2: Response Quality (DistilBERT)"),
        ("classifier3_emotion", "Classifier 3: Emotion + Pressure (DistilBERT)"),
    ]:
        state = load_trainer_state(name)
        if state:
            train_data, eval_data = extract_metrics(state)
            if eval_data:
                plot_classifier(name, title, train_data, eval_data,
                                os.path.join(OUTPUT_DIR, f"{name}_curves.png"))
            else:
                print(f"  {name}: no eval data found")
        else:
            print(f"  {name}: no trainer_state.json found (training may still be running)")

    # Comparison bar chart
    plot_comparison_bar(os.path.join(OUTPUT_DIR, "accuracy_comparison.png"))

    # Dataset composition
    plot_dataset_composition(os.path.join(OUTPUT_DIR, "dataset_composition.png"))

    print(f"\nAll plots saved to: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
