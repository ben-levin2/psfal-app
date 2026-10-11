"""Copyable tables: a collapsed section under a dashboard table holding the same rows as tab-separated text, headers first.

The text is built from the DataFrame that is already on screen, so nothing is recalculated. Streamlit's code block supplies the copy button, and
tab-separated text pastes into Excel, Google Sheets and Numbers as separate columns.
"""
import pandas as pd
import streamlit as st

LABEL = "Copy this table (paste into a spreadsheet)"


def _cell(v):
    """One cell as text. Missing values become empty cells; tabs and line breaks become spaces so a cell cannot split a row or column."""
    if v is None or (not isinstance(v, (list, tuple, dict)) and pd.isna(v)):
        return ""
    return " ".join(str(v).replace("\t", " ").splitlines())


def to_tsv(df):
    """Tab-separated text of a DataFrame: one header line, then one line per row, in the order shown. The index is left out, as on screen."""
    lines = ["\t".join(_cell(c) for c in df.columns)]
    lines += ["\t".join(_cell(v) for v in row) for row in df.itertuples(index=False, name=None)]
    return "\n".join(lines)


def copy_section(df, label=LABEL):
    """Collapsed section with the table as tab-separated text and a copy button. Call it right after the matching st.dataframe."""
    with st.expander(label, expanded=False):
        st.code(to_tsv(df), language=None)
