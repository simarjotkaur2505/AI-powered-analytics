"""
Tests for src/charts.py

Covers: pick_chart_type heuristics, ID column filtering,
        render_chart return types, and edge cases.
Run:  pytest tests/test_charts.py -v
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.charts import (
    _is_id_col,
    _numeric_cols,
    _non_numeric_cols,
    pick_chart_type,
    render_chart,
)


# ── Helper DataFrames ─────────────────────────────────────────────────────────

def df_time_series():
    return pd.DataFrame({
        "month":   ["2025-01", "2025-02", "2025-03"],
        "revenue": [10000.0, 12000.0, 11500.0],
    })

def df_categorical():
    return pd.DataFrame({
        "category": ["Electronics", "Apparel", "Home"],
        "revenue":  [50000.0, 30000.0, 20000.0],
    })

def df_kpi_single():
    return pd.DataFrame({"total_revenue": [99999.99]})

def df_two_numerics():
    return pd.DataFrame({
        "orders":  [10, 20, 30, 40],
        "revenue": [100.0, 200.0, 300.0, 400.0],
    })

def df_with_id_and_numeric():
    """Simulates the top-customers query result that has customer_id + revenue."""
    return pd.DataFrame({
        "customer_id": [703, 907, 978, 545, 992],
        "name":        ["Alice", "Bob", "Carol", "Dan", "Eve"],
        "revenue":     [48551.35, 41907.63, 39959.03, 37406.38, 35722.75],
    })

def df_many_categories():
    return pd.DataFrame({
        "country": [f"Country{i}" for i in range(12)],
        "revenue": [float(i * 1000) for i in range(1, 13)],
    })

def df_empty():
    return pd.DataFrame()


# ── _is_id_col ────────────────────────────────────────────────────────────────

class TestIsIdCol:
    @pytest.mark.parametrize("col", [
        "customer_id", "order_id", "product_id", "item_id",
        "user_key", "ref_no", "record_num", "account_number", "postal_code",
        "id",
    ])
    def test_identifies_id_columns(self, col):
        assert _is_id_col(col) is True

    @pytest.mark.parametrize("col", [
        "revenue", "quantity", "unit_price", "total",
        "name", "country", "category", "month", "segment",
    ])
    def test_does_not_flag_value_columns(self, col):
        assert _is_id_col(col) is False


# ── _numeric_cols ─────────────────────────────────────────────────────────────

class TestNumericCols:
    def test_excludes_id_columns(self):
        df = df_with_id_and_numeric()
        cols = _numeric_cols(df)
        assert "customer_id" not in cols
        assert "revenue" in cols

    def test_returns_all_numeric_when_no_ids(self):
        df = df_two_numerics()
        cols = _numeric_cols(df)
        assert set(cols) == {"orders", "revenue"}

    def test_fallback_returns_id_col_if_only_numeric(self):
        """If the only numeric column is an ID, it should still be returned."""
        df = pd.DataFrame({"customer_id": [1, 2, 3]})
        cols = _numeric_cols(df)
        assert "customer_id" in cols

    def test_kpi_single_numeric(self):
        df = df_kpi_single()
        cols = _numeric_cols(df)
        assert cols == ["total_revenue"]


# ── pick_chart_type: core heuristics ─────────────────────────────────────────

class TestPickChartType:
    def test_line_for_time_series(self):
        assert pick_chart_type(df_time_series()) == "line"

    def test_bar_for_categorical(self):
        assert pick_chart_type(df_categorical()) == "bar"

    def test_metric_for_single_kpi(self):
        assert pick_chart_type(df_kpi_single()) == "metric"

    def test_scatter_for_two_numerics(self):
        assert pick_chart_type(df_two_numerics()) == "scatter"

    def test_empty_dataframe_returns_empty(self):
        assert pick_chart_type(df_empty()) == "empty"

    def test_id_column_ignored_picks_bar_not_scatter(self):
        """customer_id should be excluded so only 'revenue' remains → bar (not scatter)."""
        assert pick_chart_type(df_with_id_and_numeric()) == "bar"

    def test_line_takes_priority_over_bar(self):
        """A DataFrame with both a date col and a category col should still be line."""
        df = pd.DataFrame({
            "month":    ["2025-01", "2025-02"],
            "category": ["Electronics", "Apparel"],
            "revenue":  [1000.0, 2000.0],
        })
        assert pick_chart_type(df) == "line"

    def test_metric_requires_single_row(self):
        """Two rows with one numeric col should NOT be metric."""
        df = pd.DataFrame({"revenue": [100.0, 200.0]})
        result = pick_chart_type(df)
        assert result != "metric"

    def test_date_hint_variants(self):
        """Various date-like column names should trigger line chart."""
        for col in ["order_date", "signup_year", "week", "quarter", "period"]:
            df = pd.DataFrame({col: ["2025-01", "2025-02"], "revenue": [100.0, 200.0]})
            assert pick_chart_type(df) == "line", f"Failed for column: {col}"

    def test_category_hint_variants(self):
        """Various category-like column names should trigger bar chart."""
        for col in ["country", "segment", "status", "region", "type"]:
            df = pd.DataFrame({col: ["A", "B", "C"], "revenue": [1.0, 2.0, 3.0]})
            assert pick_chart_type(df) == "bar", f"Failed for column: {col}"


# ── render_chart ──────────────────────────────────────────────────────────────

class TestRenderChart:
    def test_line_returns_figure(self):
        fig = render_chart(df_time_series(), "line")
        assert isinstance(fig, go.Figure)

    def test_bar_returns_figure(self):
        fig = render_chart(df_categorical(), "bar")
        assert isinstance(fig, go.Figure)

    def test_scatter_returns_figure(self):
        fig = render_chart(df_two_numerics(), "scatter")
        assert isinstance(fig, go.Figure)

    def test_metric_returns_none(self):
        assert render_chart(df_kpi_single(), "metric") is None

    def test_empty_returns_none(self):
        assert render_chart(df_empty(), "empty") is None

    def test_empty_df_returns_none_regardless_of_type(self):
        assert render_chart(df_empty(), "bar") is None

    def test_many_categories_renders_horizontal_bar(self):
        """More than 8 rows triggers horizontal bar orientation."""
        fig = render_chart(df_many_categories(), "bar")
        assert isinstance(fig, go.Figure)
        # Horizontal bar traces have orientation="h"
        assert fig.data[0].orientation == "h"

    def test_few_categories_renders_vertical_bar(self):
        """≤8 rows renders a vertical bar (no orientation attribute = vertical)."""
        fig = render_chart(df_categorical(), "bar")
        assert isinstance(fig, go.Figure)
        assert fig.data[0].orientation != "h"

    def test_figure_has_white_background(self):
        fig = render_chart(df_time_series(), "line")
        assert fig.layout.plot_bgcolor == "white"
        assert fig.layout.paper_bgcolor == "white"

    def test_bar_chart_excludes_id_column(self):
        """Bar chart should plot revenue on Y axis, not customer_id."""
        df = df_with_id_and_numeric()
        fig = render_chart(df, "bar")
        assert isinstance(fig, go.Figure)
        # The Y axis title should be Revenue, not Customer Id
        yaxis_title = fig.layout.yaxis.title.text if fig.layout.yaxis.title else None
        # Plotly Express uses the col name as y title via labels dict
        assert fig.data[0].y is not None
        y_values = list(fig.data[0].y)
        # Y values should be revenue-scale (thousands), not ID-scale (< 1000)
        assert max(y_values) > 1000

    def test_unknown_chart_type_returns_table_figure(self):
        """Fallback for unknown chart type is a Plotly Table."""
        fig = render_chart(df_categorical(), "unknown_type")
        assert isinstance(fig, go.Figure)
        assert isinstance(fig.data[0], go.Table)
