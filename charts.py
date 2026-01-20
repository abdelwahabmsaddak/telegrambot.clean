# charts.py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def plot_closes_image(title: str, closes, out_path: str):
    plt.figure(figsize=(9, 3))
    plt.plot(list(range(len(closes))), closes)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(out_path, dpi=170)
    plt.close()
    return out_path
