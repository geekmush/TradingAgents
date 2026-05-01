"""
Options Strategist Agent.

This agent translates the Portfolio Manager's directional thesis into a specific,
executable options trade using operational tools from the OTB engine.
"""

from typing import Annotated, Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from tradingagents.agents.schemas import OptionsTrade, render_options_trade
from tradingagents.agents.utils.options_tools import (
    validate_with_otb_engine,
    get_options_chain,
    get_iv_context,
    get_strategy_backtest,
)

def create_options_strategist(llm: Any):
    """
    Creates the Options Strategist agent node.
    """
    # Bind the specialized tools
    tools = [
        validate_with_otb_engine,
        get_options_chain,
        get_iv_context,
        get_strategy_backtest,
    ]
    llm_with_tools = llm.bind_tools(tools)

    def node(state):
        # The Options Strategist consumes the final_trade_decision (Portfolio Manager output)
        # and the original thesis context.
        pm_decision = state["final_trade_decision"]
        ticker = state["company_of_interest"]

        system_prompt = f"""You are the Options Strategist. Your goal is to translate the Portfolio Manager's thesis for {ticker} into a precise, executable options trade.

        CRIITICAL OPERATIONAL RULES:
        1. Do NOT hallucinate strikes or expirations. Always use `get_options_chain`.
        2. Use `get_iv_context` to determine the IV regime (Low, Normal, High).
        3. Use `get_strategy_backtest` to find the strategy with the highest edge for this ticker and regime.
        4. You MUST call `validate_with_otb_engine` on your final proposal. If it is rejected, you must adjust the strikes or strategy and re-validate.
        5. Sizing: Max loss must be <= 2% of portfolio NAV and <= 100% of intended notional.

        If no trade can be constructed that satisfies the risk and liquidity constraints, you MUST explicitly state that "no good option chain entrypoints are available" and explain why (e.g., liquidity, risk cap, or IV regime).

        Input Thesis:
        {pm_decision}
        """

        # We use a simple loop for tool-use within the node, or we could rely on the
        # graph's tool_node if we wanted a more complex interaction.
        # For the Strategist, we'll use a refined prompt to encourage structured tool usage.

        # Note: In the actual graph, this node will be followed by a tool node if
        # the agent decides to use tools.

        messages = [
            HumanMessage(content=system_prompt)
        ]

        # Append conversation history if available in state
        if "messages" in state:
            messages = state["messages"] + messages

        response = llm_with_tools.invoke(messages)

        # We return the response and a flag to indicate if we need to go to tools
        return {
            "messages": [response],
            "options_trade": None # This will be populated after validation and rendering
        }

    return node
