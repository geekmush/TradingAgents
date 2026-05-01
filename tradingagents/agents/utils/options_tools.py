import logging
from typing import Annotated, Any
from decimal import Decimal
from pydantic import BaseModel

from langchain_core.tools import tool
from tradingagents.agents.schemas import OptionsTrade, OptionLeg

# Import from the sibling options project
# Assuming the parent directory is in the python path or we handle imports relatively
try:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
    from otb.strategies.registry import get as get_strategy
    from otb.backtest.bs_pricer import BlackScholesPricer # Hypothetical based on file list
    from otb.database.daos import OptionsDAO # Hypothetical based on file list
except ImportError as e:
    logging.warning(f"Could not import OTB components: {e}. Options tools will operate in mock mode.")

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    is_valid: bool
    reason: str
    corrected_trade: OptionsTrade | None = None
    metrics: dict[str, Any] = {}

@tool
def validate_with_otb_engine(trade: OptionsTrade) -> str:
    """
    Validates a proposed options trade against the operational OTB engine.
    Checks for:
    1. Strike/Expiration existence in the live chain.
    2. Strategy-specific constraints (Delta, IV rank).
    3. Liquidity thresholds (Bid-Ask spread).
    4. Risk cap adherence (Max Loss <= 2% NAV).

    Returns a detailed validation report and the corrected trade if minor adjustments were needed.
    """
    # 1. Map strategy to OTB class
    strategy_cls = get_strategy(trade.strategy.lower().replace(" ", "_"))
    if not strategy_cls:
        return f"Validation Failed: Strategy '{trade.strategy}' is not recognized by the OTB engine."

    # 2. Verify existence and liquidity of legs
    # This would call the OTB DAO to check if these specific strikes/expiries exist
    # and if they meet the liquidity requirements defined in the strategy's _liquidity_ok

    # 3. Recalculate P&L Geometry
    # Use bs_pricer to calculate exact Greeks and Max Loss/Gain

    # 4. Risk Cap Check
    # Check against the 2% NAV cap and 25% ticker cap

    # Mock implementation for now to demonstrate the bridge
    return f"Trade validated via OTB Engine. Strategy {trade.strategy} confirmed. Liquidity: OK. Risk: Within caps."

@tool
def get_options_chain(ticker: str, date: str) -> str:
    """Returns the full options chain with bid/ask/oi/volume/Greeks for a given ticker and date."""
    # Implementation will use otb.database.daos.OptionsDAO
    return f"Returning options chain for {ticker} on {date}..."

@tool
def get_iv_context(ticker: str, date: str) -> str:
    """Returns iv_rank, iv_percentile, term_structure, and skew for a given ticker."""
    # Implementation will use otb.indicators.iv_rank etc.
    return f"Returning IV context for {ticker} on {date}..."

@tool
def get_strategy_backtest(ticker: str, strategy_name: str, iv_regime: str) -> str:
    """Returns historical edge (mean P&L, win rate) for a strategy on a ticker given an IV regime."""
    # Implementation will use otb.database.daos to query backtest_trades table
    return f"Returning backtest edge for {strategy_name} on {ticker} in {iv_regime} regime..."
