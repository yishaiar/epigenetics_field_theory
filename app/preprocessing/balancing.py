"""GFP-high balancing workflow copied from main1.ipynb cell 31."""

import pandas as pd


def subsample_gfp_high(
    data: pd.DataFrame,
    subsample: bool,
    use_labels: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Optionally subsample GFP-high cells and summarize before/after counts.

    1. Group samples by experiment, condition, and optionally subtype.
    2. If enabled, sample each group to the smallest group size per experiment.
    3. Return selected rows and a summary with sample and aggregate counts.

    Args:
        data: Z-scored dataframe that already contains only GFP-high cells.
        subsample: Whether to balance sample sizes within each experiment.
        use_labels: Whether subtype labels are included in balancing groups.

    Returns:
        Selected dataframe and a count summary. Aggregate rows have no
        ``sample_name`` and sum over samples in each group.
    """
    group_columns = ["experiment", "condition", *(["labels"] if use_labels else []), "sample_name"]
    if subsample:
        selected_groups = []
        for _, experiment_data in data.groupby("experiment", sort=True):
            sample_groups = experiment_data.groupby(group_columns[1:], sort=True, dropna=False)
            target_size = int(sample_groups.size().min())
            selected_groups.extend(
                group.sample(n=target_size, replace=False, random_state=42 + index)
                for index, (_, group) in enumerate(sample_groups)
            )
        selected_data = pd.concat(selected_groups, ignore_index=True)
    else:
        selected_data = data

    summary: pd.DataFrame = data.groupby(group_columns, dropna=False, sort=True).size().to_frame()
    summary.columns = ["n_before"]
    selected_summary = (
        selected_data.groupby(group_columns, dropna=False, sort=True).size().to_frame()
    )
    selected_summary.columns = ["n_selected"]
    summary = summary.join(selected_summary).fillna({"n_selected": 0}).reset_index()
    summary["n_selected"] = summary["n_selected"].astype(int)
    aggregate_summary = (
        summary.groupby(group_columns[:-1], dropna=False, sort=True)[["n_before", "n_selected"]]
        .sum()
        .reset_index()
    )
    aggregate_summary["sample_name"] = pd.NA
    summary = pd.concat([aggregate_summary, summary], ignore_index=True)
    sort_columns = ["experiment", *(["labels"] if use_labels else []), "condition", "sample_name"]
    summary["_sample_sort"] = summary["sample_name"].notna()
    summary = (
        summary.set_index([*sort_columns[:-1], "_sample_sort", "sample_name"])
        .sort_index()
        .reset_index()
        .drop(columns="_sample_sort")
    )
    summary = summary.loc[:, ["n_before", "n_selected", *group_columns]]
    return selected_data, summary
