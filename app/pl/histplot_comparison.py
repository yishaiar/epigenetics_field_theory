from typing import Any

import matplotlib.pyplot as plt
import seaborn as sns


def histplot_comparison(
    sample1: Any,
    sample2: Any,
    title1: str,
    title2: str,
    num_samples: int = 10000,
    fname: str | None = None,
) -> None:
    if num_samples < 1:
        raise ValueError("num_samples must be positive.")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    num_bins = max(1, num_samples // (50 if num_samples > 1000 else 20))
    sns.histplot(sample1, color="r", bins=num_bins, ax=axes[0])
    axes[0].set_title(title1)

    sns.histplot(sample2, color="g", bins=num_bins, ax=axes[1])
    axes[1].set_title(title2)

    plt.tight_layout()

    if fname is not None:
        fig.savefig(f"{fname}.png", bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    from ..datasets import get_sample_data, load_demo

    def get_pairs(batch_index: int, marker_index: int) -> tuple[Any, Any]:
        batch_obs = adata.obs[adata.obs["batch_index"] == batch_index]

        anchor_sample = batch_obs.loc[batch_obs["is_anchor"], "sample_index"].iloc[0]
        other_sample = batch_obs.loc[~batch_obs["is_anchor"], "sample_index"].iloc[0]

        return (
            get_sample_data(adata, batch_index, anchor_sample)[:, marker_index],
            get_sample_data(adata, batch_index, other_sample)[:, marker_index],
        )

    adata = load_demo()
    marker_index = 0
    marker_name = str(adata.var_names[marker_index])
    anchor_batch1, sample_batch1 = get_pairs(batch_index=0, marker_index=marker_index)

    histplot_comparison(
        sample1=anchor_batch1,
        sample2=sample_batch1,
        title1=f"Anchor 1 ({marker_name})",
        title2=f"Anchor 2 ({marker_name})",
        num_samples=100,
        # fname = f"412a_{'simulation' if simulation else 'real_data'}",
    )
