import os

import matplotlib.pyplot as plt


def save_figure(fig, output_dir, filename, dpi=300):
    """Tight-layout, save, and close a matplotlib figure. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    print(f"Saved {path}")
    return path
