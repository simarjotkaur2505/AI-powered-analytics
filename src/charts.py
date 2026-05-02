"""
Chart selection heuristic and Plotly renderers.
"""

import logging

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# Column-name hints that suggest time-series data
_DATE_HINTS = {"month", "year", "date", "week", "quarter", "period", "day"}

# Column-name hints that suggest categorical data
_CAT_HINTS = {
    "name", "country", "category", "segment", "status",
    "product", "customer", "region", "type",
}


def _is_date_col(col: str) -> bool:
    return any(h in col.lower() for h in _DATE_HINTS)


def _is_cat_col(col: str) -> bool:
    return any(h in col.lower() for h in _CAT_HINTS)


# Column-name suffixes that indicate ID/key columns — not useful as chart values
_ID_HINTS = {"_id", "_key", "_no", "_num", "_number", "_code"}


def _is_id_col(col: str) -> bool:
    col_lower = col.lower()
    return col_lower == "id" or any(col_lower.endswith(h) for h in _ID_HINTS)


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    """Returns numeric columns, skipping obvious ID/key columns."""
    all_num = df.select_dtypes(include="number").columns.tolist()
    # Prefer non-ID columns; fall back to all numeric if none remain
    non_id = [c for c in all_num if not _is_id_col(c)]
    return non_id if non_id else all_num


def _non_numeric_cols(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(exclude="number").columns.tolist()


# ── Chart type picker ─────────────────────────────────────────────────────────

def pick_chart_type(df: pd.DataFrame) -> str:
    """
    Heuristic rules (in priority order):

    1. Has a date/time column + ≥1 numeric  → line
    2. Single row, single numeric            → metric (KPI card)
    3. 1 categorical + 1 numeric column     → bar
    4. 2 numeric columns                    → scatter
    5. Fallback                             → bar
    """
    if df.empty:
        return "empty"

    num_cols = _numeric_cols(df)
    non_num_cols = _non_numeric_cols(df)

    # Rule 1: time-series
    date_cols = [c for c in non_num_cols if _is_date_col(c)]
    if date_cols and num_cols:
        logger.debug("pick_chart_type → line (date col: %s)", date_cols[0])
        return "line"

    # Rule 2: single KPI
    if len(df) == 1 and len(num_cols) == 1:
        logger.debug("pick_chart_type → metric")
        return "metric"

    # Rule 3: categorical bar
    cat_cols = [c for c in non_num_cols if _is_cat_col(c)]
    if cat_cols and num_cols:
        logger.debug("pick_chart_type → bar (cat col: %s)", cat_cols[0])
        return "bar"

    # Rule 4: scatter
    if len(num_cols) >= 2:
        logger.debug("pick_chart_type → scatter")
        return "scatter"

    # Rule 5: fallback bar (first non-numeric as x)
    if non_num_cols and num_cols:
        logger.debug("pick_chart_type → bar (fallback)")
        return "bar"

    logger.debug("pick_chart_type → bar (default fallback)")
    return "bar"


# ── Renderers ─────────────────────────────────────────────────────────────────

_BRAND_COLOR = "#6366F1"   # indigo — matches the app theme
_PALETTE = px.colors.qualitative.Pastel


def render_chart(df: pd.DataFrame, chart_type: str) -> go.Figure | None:
    """
    Returns a Plotly Figure or None if chart_type is 'empty' / 'metric'.
    """
    if chart_type == "empty" or df.empty:
        return None

    if chart_type == "metric":
        return None  # handled separately in the UI as st.metric

    num_cols = _numeric_cols(df)
    non_num_cols = _non_numeric_cols(df)

    if chart_type == "line":
        date_cols = [c for c in non_num_cols if _is_date_col(c)]
        x_col = date_cols[0] if date_cols else df.columns[0]
        y_col = num_cols[0]
        fig = px.line(
            df, x=x_col, y=y_col,
            markers=True,
            color_discrete_sequence=[_BRAND_COLOR],
            labels={x_col: x_col.replace("_", " ").title(),
                    y_col: y_col.replace("_", " ").title()},
        )
        fig.update_traces(line=dict(width=2.5))

    elif chart_type == "bar":
        cat_cols = [c for c in non_num_cols if _is_cat_col(c)]
        x_col = cat_cols[0] if cat_cols else (non_num_cols[0] if non_num_cols else df.columns[0])
        y_col = num_cols[0]
        # Horizontal bar when there are many categories (> 8)
        if len(df) > 8:
            fig = px.bar(
                df.sort_values(y_col, ascending=True),
                x=y_col, y=x_col,
                orientation="h",
                color_discrete_sequence=[_BRAND_COLOR],
                labels={x_col: x_col.replace("_", " ").title(),
                        y_col: y_col.replace("_", " ").title()},
            )
        else:
            fig = px.bar(
                df.sort_values(y_col, ascending=False),
                x=x_col, y=y_col,
                color_discrete_sequence=[_BRAND_COLOR],
                labels={x_col: x_col.replace("_", " ").title(),
                        y_col: y_col.replace("_", " ").title()},
            )

    elif chart_type == "scatter":
        x_col = num_cols[0]
        y_col = num_cols[1]
        color_col = non_num_cols[0] if non_num_cols else None
        fig = px.scatter(
            df, x=x_col, y=y_col,
            color=color_col,
            color_discrete_sequence=_PALETTE,
            labels={x_col: x_col.replace("_", " ").title(),
                    y_col: y_col.replace("_", " ").title()},
        )

    else:
        # Last-resort: table chart
        fig = go.Figure(data=[go.Table(
            header=dict(values=list(df.columns), fill_color="#6366F1", font_color="white"),
            cells=dict(values=[df[c] for c in df.columns]),
        )])

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, sans-serif", size=13),
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig
