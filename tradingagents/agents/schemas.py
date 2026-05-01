"""Pydantic schemas used by agents that produce structured output.

The framework's primary artifact is still prose: each agent's natural-language
reasoning is what users read in the saved markdown reports and what the
downstream agents read as context.  Structured output is layered onto the
three decision-making agents (Research Manager, Trader, Portfolio Manager)
so that:

- Their outputs follow consistent section headers across runs and providers
- Each provider's native structured-output mode is used (json_schema for
  OpenAI/xAI, response_schema for Gemini, tool-use for Anthropic)
- Schema field descriptions become the model's output instructions, freeing
  the prompt body to focus on context and the rating-scale guidance
- A render helper turns the parsed Pydantic instance back into the same
  markdown shape the rest of the system already consumes, so display,
  memory log, and saved reports keep working unchanged
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared rating types
# ---------------------------------------------------------------------------


class PortfolioRating(str, Enum):
    """5-tier rating used by the Research Manager and Portfolio Manager."""

    BUY = "Buy"
    OVERWEIGHT = "Overweight"
    HOLD = "Hold"
    UNDERWEIGHT = "Underweight"
    SELL = "Sell"


class TraderAction(str, Enum):
    """3-tier transaction direction used by the Trader.

    The Trader's job is to translate the Research Manager's investment plan
    into a concrete transaction proposal: should the desk execute a Buy, a
    Sell, or sit on Hold this round.  Position sizing and the nuanced
    Overweight / Underweight calls happen later at the Portfolio Manager.
    """

    BUY = "Buy"
    HOLD = "Hold"
    SELL = "Sell"


# ---------------------------------------------------------------------------
# Research Manager
# ---------------------------------------------------------------------------


class ResearchPlan(BaseModel):
    """Structured investment plan produced by the Research Manager.

    Hand-off to the Trader: the recommendation pins the directional view,
    the rationale captures which side of the bull/bear debate carried the
    argument, and the strategic actions translate that into concrete
    instructions the trader can execute against.
    """

    recommendation: PortfolioRating = Field(
        description=(
            "The investment recommendation. Exactly one of Buy / Overweight / "
            "Hold / Underweight / Sell. Reserve Hold for situations where the "
            "evidence on both sides is genuinely balanced; otherwise commit to "
            "the side with the stronger arguments."
        ),
    )
    rationale: str = Field(
        description=(
            "Conversational summary of the key points from both sides of the "
            "debate, ending with which arguments led to the recommendation. "
            "Speak naturally, as if to a teammate."
        ),
    )
    strategic_actions: str = Field(
        description=(
            "Concrete steps for the trader to implement the recommendation, "
            "including position sizing guidance consistent with the rating."
        ),
    )


def render_research_plan(plan: ResearchPlan) -> str:
    """Render a ResearchPlan to markdown for storage and the trader's prompt context."""
    return "\n".join([
        f"**Recommendation**: {plan.recommendation.value}",
        "",
        f"**Rationale**: {plan.rationale}",
        "",
        f"**Strategic Actions**: {plan.strategic_actions}",
    ])


# ---------------------------------------------------------------------------
# Trader
# ---------------------------------------------------------------------------


class TraderProposal(BaseModel):
    """Structured transaction proposal produced by the Trader.

    The trader reads the Research Manager's investment plan and the analyst
    reports, then turns them into a concrete transaction: what action to
    take, the reasoning that justifies it, and the practical levels for
    entry, stop-loss, and sizing.
    """

    action: TraderAction = Field(
        description="The transaction direction. Exactly one of Buy / Hold / Sell.",
    )
    reasoning: str = Field(
        description=(
            "The case for this action, anchored in the analysts' reports and "
            "the research plan. Two to four sentences."
        ),
    )
    entry_price: Optional[float] = Field(
        default=None,
        description="Optional entry price target in the instrument's quote currency.",
    )
    stop_loss: Optional[float] = Field(
        default=None,
        description="Optional stop-loss price in the instrument's quote currency.",
    )
    position_sizing: Optional[str] = Field(
        default=None,
        description="Optional sizing guidance, e.g. '5% of portfolio'.",
    )


def render_trader_proposal(proposal: TraderProposal) -> str:
    """Render a TraderProposal to markdown.

    The trailing ``FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL**`` line is
    preserved for backward compatibility with the analyst stop-signal text
    and any external code that greps for it.
    """
    parts = [
        f"**Action**: {proposal.action.value}",
        "",
        f"**Reasoning**: {proposal.reasoning}",
    ]
    if proposal.entry_price is not None:
        parts.extend(["", f"**Entry Price**: {proposal.entry_price}"])
    if proposal.stop_loss is not None:
        parts.extend(["", f"**Stop Loss**: {proposal.stop_loss}"])
    if proposal.position_sizing:
        parts.extend(["", f"**Position Sizing**: {proposal.position_sizing}"])
    parts.extend([
        "",
        f"FINAL TRANSACTION PROPOSAL: **{proposal.action.value.upper()}**",
    ])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Portfolio Manager
# ---------------------------------------------------------------------------


class PortfolioDecision(BaseModel):
    """Structured output produced by the Portfolio Manager.

    The model fills every field as part of its primary LLM call; no separate
    extraction pass is required. Field descriptions double as the model's
    output instructions, so the prompt body only needs to convey context and
    the rating-scale guidance.
    """

    rating: PortfolioRating = Field(
        description=(
            "The final position rating. Exactly one of Buy / Overweight / Hold / "
            "Underweight / Sell, picked based on the analysts' debate."
        ),
    )
    executive_summary: str = Field(
        description=(
            "A concise action plan covering entry strategy, position sizing, "
            "key risk levels, and time horizon. Two to four sentences."
        ),
    )
    investment_thesis: str = Field(
        description=(
            "Detailed reasoning anchored in specific evidence from the analysts' "
            "debate. If prior lessons are referenced in the prompt context, "
            "incorporate them; otherwise rely solely on the current analysis."
        ),
    )
    price_target: Optional[float] = Field(
        default=None,
        description="Optional target price in the instrument's quote currency.",
    )
    time_horizon: Optional[str] = Field(
        default=None,
        description="Optional recommended holding period, e.g. '3-6 months'.",
    )


def render_pm_decision(decision: PortfolioDecision) -> str:
    """Render a PortfolioDecision back to the markdown shape the rest of the system expects.

    Memory log, CLI display, and saved report files all read this markdown,
    so the rendered output preserves the exact section headers (``**Rating**``,
    ``**Executive Summary**``, ``**Investment Thesis**``) that downstream
    parsers and the report writers already handle.
    """
    parts = [
        f"**Rating**: {decision.rating.value}",
        "",
        f"**Executive Summary**: {decision.executive_summary}",
        "",
        f"**Investment Thesis**: {decision.investment_thesis}",
    ]
    if decision.price_target is not None:
        parts.extend(["", f"**Price Target**: {decision.price_target}"])
    if decision.time_horizon:
        parts.extend(["", f"**Time Horizon**: {decision.time_horizon}"])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Options Strategist
# ---------------------------------------------------------------------------


class OptionLeg(BaseModel):
    """A single leg of an options trade."""
    action: str = Field(description="buy | sell")
    type: str = Field(description="call | put")
    strike: float = Field(description="The strike price of the option")
    expiration: str = Field(description="Expiration date in YYYY-MM-DD format")
    quantity: int = Field(description="Number of contracts")


class OptionsTrade(BaseModel):
    """Structured options trade produced by the Options Strategist.

    This model matches the operational requirements of the OTB engine and
    is used to bridge the directional thesis to an executable trade.
    """
    strategy: str = Field(description="Name of the strategy, e.g., 'Bull Call Debit Spread'")
    direction: str = Field(description="bullish | bearish | neutral | hedge")
    underlying: str = Field(description="Ticker symbol of the underlying asset")
    legs: list[OptionLeg] = Field(description="List of legs constituting the trade")
    debit_or_credit: str = Field(description="debit | credit")
    net_premium: float = Field(description="Net premium per contract (positive for debit, negative for credit)")
    max_loss: float = Field(description="Total maximum loss for the position")
    max_gain: Optional[float] = Field(default=None, description="Total maximum gain (null if unbounded)")
    breakevens: list[float] = Field(description="List of breakeven price levels")
    delta: float = Field(description="Portfolio delta of the trade")
    theta: float = Field(description="Portfolio theta of the trade")
    vega: float = Field(description="Portfolio vega of the trade")
    expected_pnl_at_target: float = Field(description="Expected P&L if price_target is hit at expiration")
    horizon_alignment: str = Field(description="Justification for the chosen expiration relative to time_horizon")
    liquidity_check: dict = Field(description="Details on leg liquidity (e.g., worst_leg_spread_bps, liquidity_decile)")
    historical_edge: dict = Field(description="Backtest metrics from TimescaleDB (e.g., mean_pnl, win_rate)")
    catalyst_handling: str = Field(description="Note on how binary catalysts are managed")
    notes: str = Field(description="Concise reasoning for this specific structure")


def render_options_trade(trade: OptionsTrade) -> str:
    """Render an OptionsTrade to markdown for reporting and memory logs."""
    legs_md = "\n".join([f"- {leg.action.upper()} {leg.quantity}x {leg.type.upper()} @ {leg.strike} ({leg.expiration})" for leg in trade.legs])
    return "\n".join([
        f"**Strategy**: {trade.strategy}",
        f"**Direction**: {trade.direction.capitalize()}",
        f"**Underlying**: {trade.underlying}",
        "",
        f"**Legs**:\n{legs_md}",
        "",
        f"**Financials**: {trade.debit_or_credit.capitalize()} {abs(trade.net_premium)} | Max Loss: {trade.max_loss} | Max Gain: {trade.max_gain or 'Unbounded'}",
        f"**Greeks**: Delta: {trade.delta}, Theta: {trade.theta}, Vega: {trade.vega}",
        f"**Target P&L**: {trade.expected_pnl_at_target}",
        "",
        f"**Horizon Alignment**: {trade.horizon_alignment}",
        f"**Historical Edge**: {trade.historical_edge.get('win_rate', 'N/A')} win rate over {trade.historical_edge.get('trades_in_sample', 'N/A')} trades",
        f"**Notes**: {trade.notes}",
    ])
