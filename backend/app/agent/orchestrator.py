import json
import os
import re
import urllib.request
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from . import memory, prompts, tools


class AgentState(TypedDict, total=False):
    session_id: str
    user_message: str
    loop_count: int
    tool_name: str | None
    tool_args: dict
    tool_result: dict | None
    final_response: str | None
    pending_confirmation: dict | None
    stop: bool


def query_ollama(messages: list) -> str | None:
    """Call the local Ollama chat endpoint with the requested agent model."""
    try:
        url = "http://localhost:11434/api/chat"
        model_name = os.environ.get("OLLAMA_MODEL", "lfm2.5:8b-toolfix")
        req_body = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1},
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(req_body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("message", {}).get("content")
    except Exception as exc:
        print(f"Ollama invocation failed: {exc}")
        return None


def query_openai(messages: list) -> str | None:
    """Call an OpenAI-compatible chat endpoint when an API key is configured."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        endpoint = f"{base_url}/chat/completions"
        req_body = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(req_body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("choices", [{}])[0].get("message", {}).get("content")
    except Exception as exc:
        print(f"OpenAI invocation failed: {exc}")
        return None


def query_llm(messages: list) -> str | None:
    """Prefer an API-backed model when configured, otherwise fall back to Ollama."""
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()

    if provider in {"openai", "openai-compatible", "openai_compatible"}:
        return query_openai(messages) or query_ollama(messages)

    if os.environ.get("OPENAI_API_KEY"):
        return query_openai(messages) or query_ollama(messages)

    return query_ollama(messages)


def clean_and_parse_json(text: str):
    """Safely extracts and parses JSON payload from string."""
    if not text:
        return None

    text_clean = text.strip()
    if text_clean.startswith("```json"):
        text_clean = text_clean[7:]
    elif text_clean.startswith("```"):
        text_clean = text_clean[3:]

    if text_clean.endswith("```"):
        text_clean = text_clean[:-3]

    text_clean = text_clean.strip()

    try:
        return json.loads(text_clean)
    except Exception:
        first_curly = text_clean.find("{")
        last_curly = text_clean.rfind("}")
        if first_curly != -1 and last_curly != -1:
            try:
                return json.loads(text_clean[first_curly:last_curly + 1])
            except Exception:
                return None
        return None


def _build_messages(session_id: str, user_message: str) -> list:
    messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]
    history = memory.get_history(session_id)
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def _is_confirmation_message(text: str) -> bool:
    msg = text.lower().strip()
    return any(phrase in msg for phrase in ["confirm", "yes", "go ahead", "proceed", "approve"])


def _is_rejection_message(text: str) -> bool:
    msg = text.lower().strip()
    return any(phrase in msg for phrase in ["cancel", "no", "decline", "abort", "stop"])


def run_heuristic_agent(user_message: str, db: Session, household, session_id: str | None = None) -> tuple:
    """Fallback intelligence matching user commands to db tools."""
    msg = user_message.lower()

    if "shopping list" in msg or "restock" in msg:
        data = tools.build_shopping_list(db, household)
        if not data["shopping_list"]:
            return "No urgent restocks are needed right now.", "build_shopping_list"
        lines = ["### Suggested Shopping List"]
        for item in data["shopping_list"]:
            lines.append(f"- {item['name']} ({item['priority']}): {item['remaining_qty']} left, about {item['days_left']} days")
        return "\n".join(lines), "build_shopping_list"

    if "explain" in msg or "why" in msg:
        item_name = None
        for token in ["rice", "milk", "water"]:
            if token in msg:
                item_name = token
                break
        data = tools.explain_inventory(item_name, db, household)
        if not data["explanations"]:
            return "I couldn't find a matching inventory item to explain.", "explain_inventory"
        lines = ["### Inventory Explanation"]
        for explanation in data["explanations"]:
            lines.append(f"- {explanation['name']}: {explanation['summary']}")
        return "\n".join(lines), "explain_inventory"

    compare_match = re.search(r'(?:compare\s+prices\s+(?:of|for)|compare|price\s+of|cost\s+of|rates\s+for)\s+([a-zA-Z0-9\s]+)', msg)
    if compare_match:
        item = compare_match.group(1).strip()
        for prefix in ["prices of", "prices for", "price of", "price for", "cost of"]:
            if item.startswith(prefix + " "):
                item = item[len(prefix) + 1:].strip()
            elif item.startswith(prefix):
                item = item[len(prefix):].strip()
        data = tools.compare_prices(item, db, household)
        if not data["comparison"]:
            return f"I couldn't find any vendor prices for '{item}'. Try running `/seed/dev` to populate vendor prices first.", "compare_prices"
        result_str = f"### Where to buy {item}\n"
        for v in data["comparison"]:
            eta = f", about {v['eta_minutes']} min" if v.get("eta_minutes") is not None else ""
            result_str += f"- **{v['vendor_name']}**: ₹{v['price']}{eta}. {v['reason']}.\n"
        return result_str, "compare_prices"

    why_match = re.search(r"why\s+(?:is\s+)?([a-zA-Z0-9\s\-]+?)\s+(?:for|on)\s+([a-zA-Z0-9\s]+)", msg)
    if why_match and any(w in msg for w in ("vendor", "shop", "rank", "recommend")):
        data = tools.why_vendor(why_match.group(2).strip(), why_match.group(1).strip(), db, household)
        if not data.get("success"):
            return data["error"], "why_vendor"
        return (
            f"{data['vendor_name']} is #{data['position']} of {data['of']} for {why_match.group(2).strip()} "
            f"(you prefer {data['priority']}): ₹{data['price']}, rated {data['rating']}/5. {data['reason']}.",
            "why_vendor",
        )

    order_match = re.search(r'(?:order|buy|purchase)\s+([a-zA-Z0-9\s]+)\s+from\s+([a-zA-Z0-9\s\-]+)', msg)
    if not order_match:
        bare = re.search(r"(?:order|buy|purchase)\s+(?:some\s+|more\s+)?([a-zA-Z]+)\s*$", msg)
        if bare:
            data = tools.order_best(bare.group(1), db, household)
            if not data.get("success"):
                return data["error"], "order_best"
            chosen = data["chosen"]
            lead = f"Best option: {chosen['vendor_name']} at ₹{chosen['price']} ({chosen['reason'].lower()}). "
            return lead + data["message"], "order_best"
    if order_match:
        item = order_match.group(1).strip()
        vendor = order_match.group(2).strip()
        res = tools.place_pantry_order(item, vendor, db, household)
        if res["success"] and res.get("needs_confirmation"):
            if session_id:
                memory.set_pending_confirmation(session_id, {"order_id": res.get("order_id"), "message": res.get("message")})
            return f"⚠️ Order requires confirmation before it is finalized: {res['message']}", "place_pantry_order"
        if res["success"]:
            return f"🛍️ **Order Placed Successfully!** {res['message']} Your stock for **{item}** has been replenished to full ({res['new_remaining_qty']}).", "place_pantry_order"
        return f"❌ **Failed to place order:** {res['error']}", "place_pantry_order"

    if "household" in msg or "settings" in msg or "family" in msg:
        adults_match = re.search(r'(\d+)\s*adult', msg)
        children_match = re.search(r'(\d+)\s*child', msg)
        habit_match = re.search(r'(veg|non-veg|mixed)', msg)

        if adults_match or children_match or habit_match:
            current = tools.get_household_settings(db, household)
            adults = int(adults_match.group(1)) if adults_match else current["adults"]
            children = int(children_match.group(1)) if children_match else current["children"]
            habit = habit_match.group(1) if habit_match else current["food_habit"]

            tools.set_household_settings(adults, children, habit, db, household)
            return f"🏠 **Household Configuration Updated!** Adults: {adults}, Children: {children}, Preference: '{habit}'.", "set_household_settings"
        h = tools.get_household_settings(db, household)
        return f"🏠 **Household Config:**\n- Adults: {h['adults']}\n- Children: {h['children']}\n- Food Preference: {h['food_habit'].capitalize()}", "get_household_settings"

    if any(k in msg for k in ["inventory", "status", "stock", "pantry", "check", "items", "list"]):
        data = tools.get_pantry_status(db, household)
        if not data["inventory"]:
            return "Pantry is currently empty. Run `/seed/dev` or update an item to check.", "get_pantry_status"
        res_str = "### Pantry Stock Status\n"
        for item in data["inventory"]:
            status_emoji = "🟢" if item["status"] == "safe" else ("🟡" if item["status"] == "warning" else "🔴")
            res_str += f"- {status_emoji} **{item['name'].capitalize()}**: {item['remaining_qty']}/{item['pack_size']} {item['unit']} remaining (Est. {item['days_left']} days left) | Status: *{item['status'].upper()}*\n"
        return res_str, "get_pantry_status"

    if "vendor" in msg or "shop" in msg or "store" in msg:
        v_data = tools.get_vendors(db)
        if not v_data["vendors"]:
            return "No vendors found. Please trigger seed data first.", "get_vendors"
        res_str = "### Registered Vendors\n"
        for v in v_data["vendors"]:
            res_str += f"- **{v['name']}** ({v['vendor_type'].capitalize()}) - Rating: {v['rating']}★ ({v['review_count']} reviews)\n"
        return res_str, "get_vendors"

    default_resp = """👋 **Hello! I am your AutoBasket Smart Pantry Agent.** 🧺

I manage inventory stock levels, compare vendor catalogs/prices, build shopping lists, and tune household parameters.

Here are some commands you can type:
- *Show pantry status*
- *Compare prices for milk*
- *Explain rice*
- *Show shopping list*
- *Order rice from Blinkit*
- *Show recent orders*
- *Show household settings*

*(Operating in local heuristic routing mode)*"""
    return default_resp, "default_chat"


def _execute_tool(tool_name: str, tool_args: dict, session_id: str, db: Session, household) -> tuple[dict | None, dict | None, bool]:
    tool_result = None
    pending_confirmation = None
    stop = False

    if tool_name == "get_pantry_status":
        tool_result = tools.get_pantry_status(db, household)
    elif tool_name == "get_vendors":
        tool_result = tools.get_vendors(db)
    elif tool_name == "compare_prices":
        tool_result = tools.compare_prices(tool_args.get("item_name", ""), db, household)
    elif tool_name == "order_best":
        tool_result = tools.order_best(tool_args.get("item_name", ""), db, household)
    elif tool_name == "why_vendor":
        tool_result = tools.why_vendor(tool_args.get("item_name", ""), tool_args.get("vendor_name", ""), db, household)
    elif tool_name == "place_pantry_order":
        tool_result = tools.place_pantry_order(tool_args.get("item_name", ""), tool_args.get("vendor_name", ""), db, household)
        if tool_result.get("needs_confirmation"):
            pending_confirmation = {"order_id": tool_result.get("order_id"), "message": tool_result.get("message")}
            memory.set_pending_confirmation(session_id, pending_confirmation)
            stop = True
    elif tool_name == "confirm_pending_order":
        tool_result = tools.confirm_pending_order(int(tool_args.get("order_id", 0)), db, household)
        if tool_result.get("success"):
            memory.clear_pending_confirmation(session_id)
            stop = True
    elif tool_name == "update_item_qty":
        tool_result = tools.update_item_qty(tool_args.get("item_name", ""), float(tool_args.get("remaining_qty", 0)), db, household)
    elif tool_name == "get_household_settings":
        tool_result = tools.get_household_settings(db, household)
    elif tool_name == "set_household_settings":
        tool_result = tools.set_household_settings(
            int(tool_args.get("adults", 2)),
            int(tool_args.get("children", 1)),
            tool_args.get("food_habit", "mixed"),
            db,
            household,
        )
    elif tool_name == "get_recent_orders":
        tool_result = tools.get_recent_orders(db, household)
    elif tool_name == "build_shopping_list":
        tool_result = tools.build_shopping_list(db, household)
    elif tool_name == "explain_inventory":
        tool_result = tools.explain_inventory(tool_args.get("item_name"), db, household)
    else:
        tool_result = {"error": f"Tool '{tool_name}' is not supported."}

    return tool_result, pending_confirmation, stop


def agent_node(state: AgentState, db: Session, household) -> AgentState:
    session_id = state["session_id"]
    user_message = state["user_message"]
    pending_confirmation = memory.get_pending_confirmation(session_id)

    if pending_confirmation and _is_confirmation_message(user_message):
        state["tool_name"] = "confirm_pending_order"
        state["tool_args"] = {"order_id": pending_confirmation.get("order_id")}
        return state

    if pending_confirmation and _is_rejection_message(user_message):
        memory.clear_pending_confirmation(session_id)
        state["final_response"] = "Order cancelled. No purchase was placed."
        state["stop"] = True
        return state

    if pending_confirmation:
        state["final_response"] = f"Please confirm the pending order before I place it. {pending_confirmation.get('message')}"
        state["stop"] = True
        return state

    state["loop_count"] = state.get("loop_count", 0) + 1
    messages = _build_messages(session_id, user_message)
    raw_response = query_llm(messages)
    if not raw_response:
        heuristic_resp, _ = run_heuristic_agent(user_message, db, household, session_id)
        state["final_response"] = heuristic_resp
        state["stop"] = True
        return state

    parsed = clean_and_parse_json(raw_response)
    if not parsed:
        heuristic_resp, _ = run_heuristic_agent(user_message, db, household, session_id)
        state["final_response"] = heuristic_resp
        state["stop"] = True
        return state

    if parsed.get("tool_call"):
        state["tool_name"] = parsed["tool_call"].get("name")
        state["tool_args"] = parsed["tool_call"].get("arguments", {})
        state["tool_result"] = None
        return state

    if parsed.get("response"):
        state["final_response"] = parsed["response"]
        state["stop"] = True
        return state

    heuristic_resp, _ = run_heuristic_agent(user_message, db, household, session_id)
    state["final_response"] = heuristic_resp
    state["stop"] = True
    return state


def tool_node(state: AgentState, db: Session, household) -> AgentState:
    session_id = state["session_id"]
    tool_name = state.get("tool_name")
    tool_args = state.get("tool_args", {})

    tool_result, pending_confirmation, stop = _execute_tool(tool_name, tool_args, session_id, db, household)
    state["tool_result"] = tool_result
    state["pending_confirmation"] = pending_confirmation
    state["stop"] = stop

    if tool_result is not None:
        memory.add_message(session_id, "user", f"[TOOL RESULT]\n{json.dumps(tool_result)}")

    if pending_confirmation:
        state["final_response"] = f"Please confirm the pending order before I place it. {pending_confirmation.get('message')}"
    elif stop and tool_result:
        state["final_response"] = tool_result.get("message") or tool_result.get("error") or "Done."

    return state


def route_after_agent(state: AgentState) -> str:
    if state.get("tool_name"):
        return "tool"
    return "final"


def route_after_tool(state: AgentState) -> str:
    if state.get("stop"):
        return "final"
    if state.get("loop_count", 0) >= 3:
        return "final"
    return "agent"


def build_graph(db: Session, household):
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", lambda state: agent_node(state, db, household))
    workflow.add_node("tool", lambda state: tool_node(state, db, household))
    workflow.add_node("final", lambda state: state)
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", route_after_agent, {"tool": "tool", "final": "final"})
    workflow.add_conditional_edges("tool", route_after_tool, {"agent": "agent", "final": "final"})
    workflow.add_edge("final", END)
    return workflow.compile()


def run_agent_chat(user_message: str, session_id: str, db: Session, household) -> str:
    """Main agent orchestration loop with a LangGraph-style ReAct flow."""
    memory.add_message(session_id, "user", user_message)

    state: AgentState = {
        "session_id": session_id,
        "user_message": user_message,
        "loop_count": 0,
        "tool_name": None,
        "tool_args": {},
        "tool_result": None,
        "final_response": None,
        "pending_confirmation": None,
        "stop": False,
    }

    graph = build_graph(db, household)
    result = graph.invoke(state)
    final_response = result.get("final_response")
    if not final_response:
        final_response = "I couldn't produce a useful response."

    if final_response and not any(msg["content"] == final_response for msg in memory.get_history(session_id)[-2:]):
        memory.add_message(session_id, "assistant", final_response)

    return final_response
