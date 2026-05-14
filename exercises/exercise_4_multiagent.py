"""Bài Tập 4: Thêm Privacy Agent vào Multi-Agent System (Bao gồm 4 Thử Thách Nâng Cao)

Hoàn thành các TODO để thêm privacy agent và conditional routing.
Đã tích hợp:
1. Financial Agent
2. Conversation Memory
3. Custom Tool (Tính toán phạt tài chính)
4. Error Handling & Retry Logic
"""

import asyncio
import os
import sys
import time
from typing import Annotated, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from langchain_core.tools import tool

from common.llm import get_llm

def _last_wins(left: str | None, right: str | None) -> str:
    """Reducer: giá trị mới ghi đè giá trị cũ."""
    return right if right is not None else (left or "")

class State(TypedDict):
    chat_history: list[dict]  # Challenge 2: Conversation Memory
    question: str
    law_analysis: Annotated[str, _last_wins]
    tax_analysis: Annotated[str, _last_wins]
    compliance_analysis: Annotated[str, _last_wins]
    privacy_analysis: Annotated[str, _last_wins]
    financial_analysis: Annotated[str, _last_wins]  # Challenge 1: Financial Agent
    final_response: str

# Challenge 4: Error Handling & Retry Decorator
def retry_llm_call(max_retries=3, delay=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"⚠️ Lỗi khi xử lý: {e}. Thử lại lần {i+1}...")
                    if i == max_retries - 1:
                        return {"error": f"Lỗi không thể phục hồi: {e}"}
                    time.sleep(delay)
        return wrapper
    return decorator

@retry_llm_call()
def law_agent(state: State) -> dict:
    """Agent phân tích pháp lý tổng quát."""
    llm = get_llm()
    # Format chat history for context
    history_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state.get('chat_history', [])])
    
    prompt = f"""Bạn là chuyên gia pháp lý. Dựa vào lịch sử hội thoại (nếu có):
{history_context}

Phân tích câu hỏi mới nhất sau:
{state['question']}

Tập trung vào: hợp đồng, trách nhiệm dân sự, quyền và nghĩa vụ pháp lý."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"law_analysis": response.content}

def check_routing(state: State) -> list[Send]:
    """Quyết định gọi agents nào dựa trên nội dung câu hỏi."""
    question_lower = state["question"].lower()
    tasks = []
    
    if any(kw in question_lower for kw in ["tax", "irs", "thuế"]):
        tasks.append(Send("tax_agent", state))
    
    if any(kw in question_lower for kw in ["compliance", "sec", "regulation"]):
        tasks.append(Send("compliance_agent", state))
    
    if any(kw in question_lower for kw in ["data", "privacy", "gdpr", "dữ liệu"]):
        tasks.append(Send("privacy_agent", state))
        
    # Thêm routing cho financial_agent
    if any(kw in question_lower for kw in ["tài chính", "tiền", "phạt", "doanh thu", "thiệt hại", "financial", "penalty"]):
        tasks.append(Send("financial_agent", state))
        
    return tasks if tasks else [Send("aggregate_results", state)]

@retry_llm_call()
def tax_agent(state: State) -> dict:
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia thuế. Phân tích khía cạnh thuế trong câu hỏi:
Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}
Tập trung: IRS, tax evasion, penalties, FBAR, FATCA."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"tax_analysis": response.content}

@retry_llm_call()
def compliance_agent(state: State) -> dict:
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia compliance. Phân tích khía cạnh tuân thủ:
Câu hỏi: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}
Tập trung: SEC, SOX, FCPA, AML, regulatory violations."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"compliance_analysis": response.content}

@retry_llm_call()
def privacy_agent(state: State) -> dict:
    llm = get_llm()
    prompt = f"""Bạn là chuyên gia về GDPR và luật bảo vệ dữ liệu cá nhân.
Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}
Hãy phân tích các vấn đề về privacy và GDPR (nếu có). Tập trung: GDPR, data protection, privacy rights, data breach."""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"privacy_analysis": response.content}

# Challenge 3: Custom Tool
@tool
def calculate_financial_penalty(revenue: float, severity: str) -> str:
    """Tính toán mức phạt tài chính dựa trên doanh thu và mức độ vi phạm.
    
    Args:
        revenue: Doanh thu của công ty (USD)
        severity: Mức độ vi phạm ('low', 'medium', 'high')
    """
    rates = {"low": 0.01, "medium": 0.03, "high": 0.05}
    rate = rates.get(severity.lower(), 0.01)
    penalty = revenue * rate
    return f"Mức phạt dự kiến là {penalty:,.2f} USD (Dựa trên {rate*100}% doanh thu)."

# Challenge 1: Financial Agent
@retry_llm_call()
def financial_agent(state: State) -> dict:
    """Agent chuyên về tài chính và tính toán thiệt hại."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools([calculate_financial_penalty])
    
    prompt = f"""Bạn là chuyên gia tài chính. 
Câu hỏi gốc: {state['question']}
Phân tích pháp lý: {state.get('law_analysis', 'N/A')}

Hãy phân tích thiệt hại tài chính. Nếu có dữ liệu về doanh thu và mức độ, hãy gọi tool 'calculate_financial_penalty' để tính phạt."""
    
    messages = [SystemMessage(content="Bạn là trợ lý tài chính giỏi."), HumanMessage(content=prompt)]
    
    # Tool calling loop
    response = llm_with_tools.invoke(messages)
    if hasattr(response, "tool_calls") and response.tool_calls:
        messages.append(response)
        for tool_call in response.tool_calls:
            if tool_call["name"] == "calculate_financial_penalty":
                print(f"🔧 Financial Agent đang gọi tool tính phạt: {tool_call['args']}")
                result = calculate_financial_penalty.invoke(tool_call["args"])
                messages.append(ToolMessage(content=result, tool_call_id=tool_call["id"]))
        
        response = llm_with_tools.invoke(messages)
        
    return {"financial_analysis": response.content if hasattr(response, "content") else str(response)}

@retry_llm_call()
def aggregate_results(state: State) -> dict:
    llm = get_llm()
    sections = []
    if state.get("law_analysis"):
        sections.append(f"📋 PHÂN TÍCH PHÁP LÝ:\n{state['law_analysis']}")
    if state.get("tax_analysis"):
        sections.append(f"💰 PHÂN TÍCH THUẾ:\n{state['tax_analysis']}")
    if state.get("compliance_analysis"):
        sections.append(f"✅ PHÂN TÍCH TUÂN THỦ:\n{state['compliance_analysis']}")
    if state.get("privacy_analysis"):
        sections.append(f"🔒 PHÂN TÍCH BẢO MẬT/DỮ LIỆU:\n{state['privacy_analysis']}")
    if state.get("financial_analysis"):
        sections.append(f"💵 PHÂN TÍCH TÀI CHÍNH:\n{state['financial_analysis']}")
        
    combined = "\n\n".join(sections)
    
    prompt = f"""Tổng hợp các phân tích sau thành một báo cáo hoàn chỉnh.
Lưu ý bám sát ngữ cảnh trò chuyện trước đó (nếu có).

{combined}

Câu hỏi mới nhất: {state['question']}

Hãy tạo một báo cáo ngắn gọn, có cấu trúc rõ ràng."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"final_response": response.content}

def build_graph() -> StateGraph:
    graph = StateGraph(State)
    
    graph.add_node("law_agent", law_agent)
    graph.add_node("tax_agent", tax_agent)
    graph.add_node("compliance_agent", compliance_agent)
    graph.add_node("privacy_agent", privacy_agent)
    graph.add_node("financial_agent", financial_agent)
    graph.add_node("aggregate_results", aggregate_results)
    
    graph.add_edge(START, "law_agent")
    graph.add_conditional_edges("law_agent", check_routing)
    
    graph.add_edge("tax_agent", "aggregate_results")
    graph.add_edge("compliance_agent", "aggregate_results")
    graph.add_edge("privacy_agent", "aggregate_results")
    graph.add_edge("financial_agent", "aggregate_results")
    graph.add_edge("aggregate_results", END)
    
    return graph.compile()

async def main():
    load_dotenv()
    print("=" * 70)
    print("MULTI-AGENT SYSTEM (Đã tích hợp 4 Advanced Challenges)")
    print("1. Memory | 2. Financial Agent | 3. Custom Tools | 4. Retry Logic")
    print("=" * 70)
    print("(Gõ 'quit' hoặc 'exit' để thoát)\n")
    
    graph = build_graph()
    chat_history = []
    
    while True:
        question = input("\n👤 Bạn: ")
        if question.lower() in ['quit', 'exit']:
            break
            
        print("\n🤖 Đang xử lý qua các agents...")
        
        result = await graph.ainvoke({
            "chat_history": chat_history,
            "question": question,
            "law_analysis": "",
            "tax_analysis": "",
            "compliance_analysis": "",
            "privacy_analysis": "",
            "financial_analysis": "",
            "final_response": "",
        })
        
        final_answer = result["final_response"]
        print("\n" + "=" * 70)
        print("KẾT QUẢ CUỐI CÙNG")
        print("=" * 70)
        print(final_answer)
        
        # Lưu vào bộ nhớ
        chat_history.append({"role": "user", "content": question})
        chat_history.append({"role": "assistant", "content": final_answer})

if __name__ == "__main__":
    asyncio.run(main())
