"""Annotation attachment utility extracted verbatim from the notebook."""

import pandas as pd


def attach_annotation_labels(df: pd.DataFrame, annotation_file: str) -> pd.DataFrame:
    cols_to_add = ["labels", "leiden_labels"]
    annotation_map = pd.read_csv(
        annotation_file,
        usecols=["cell_uid", *cols_to_add],
        low_memory=False
    )
    
    # Drop existing label columns in df to avoid labels_x / labels_y collisions
    df_clean = df.drop(columns=cols_to_add, errors="ignore")
    
    n_expected = min(len(annotation_map),len(df))
    merged_df = df_clean.merge(annotation_map, on="cell_uid", how="left", indicator=True)
    n_added = (merged_df["_merge"] == "both").sum()
    merged_df = merged_df.drop(columns=["_merge"])
    
    print(f"Annotations in file: {n_expected} | Added to df: {n_added}")
    assert n_added == n_expected, (
        f"Expected all {n_expected} annotations to match, but only {n_added} were added."
    )
    
    return merged_df
