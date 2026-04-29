#!/usr/bin/env python3
"""
Test Tuần 1 — Kiểm tra công việc Team Leader + Data Engineer.

Chạy: python3 tests/test_week1.py
"""

import sys
import os

# Đảm bảo import được từ root project
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def test(name, func):
    """Chạy 1 test và ghi kết quả."""
    try:
        func()
        results.append((name, PASS, ""))
        print(f"  {PASS} {name}")
    except Exception as e:
        results.append((name, FAIL, str(e)))
        print(f"  {FAIL} {name}: {e}")


# ════════════════════════════════════════════════════════════
#  TEAM LEADER — Kiểm tra
# ════════════════════════════════════════════════════════════

# Task 1: Cấu trúc thư mục
def test_repo_structure():
    dirs = ["agent", "pipeline", "backend", "docs", "data", "infra"]
    for d in dirs:
        path = os.path.join(PROJECT_ROOT, d)
        assert os.path.isdir(path), f"Thiếu thư mục: {d}/"

test("Task 1: Cấu trúc thư mục repo", test_repo_structure)

# Task 2: Architecture Document
def test_architecture_doc():
    path = os.path.join(PROJECT_ROOT, "docs", "architecture.md")
    assert os.path.isfile(path), "Thiếu docs/architecture.md"
    content = open(path).read()
    assert len(content) > 500, "Architecture doc quá ngắn"
    assert "FastAPI" in content, "Thiếu mô tả backend"
    assert "Neo4j" in content, "Thiếu mô tả graph DB"
    assert "LangGraph" in content, "Thiếu mô tả agent framework"

test("Task 2: Architecture Document bản nháp", test_architecture_doc)

# Task 3: Graph Schema
def test_graph_schema():
    path = os.path.join(PROJECT_ROOT, "docs", "graph_schema.md")
    assert os.path.isfile(path), "Thiếu docs/graph_schema.md"
    content = open(path).read()
    # Kiểm tra có đủ Node types theo đề tài
    for node in ["Paper", "Author", "Method", "Metric", "Dataset"]:
        assert node in content, f"Thiếu Node type: {node}"
    # Kiểm tra có đủ Edge types
    for edge in ["CITES", "USES_METHOD", "AUTHORED_BY", "ACHIEVES_METRIC"]:
        assert edge in content, f"Thiếu Edge type: {edge}"

test("Task 3: Graph Schema document", test_graph_schema)

# Task 4: LangGraph framework — import được
def test_langgraph_imports():
    from langgraph.graph import StateGraph, END
    from agent.state import AgentState
    assert "messages" in AgentState.__annotations__, "AgentState thiếu field 'messages'"
    assert "plan" in AgentState.__annotations__, "AgentState thiếu field 'plan'"
    assert "user_query" in AgentState.__annotations__, "AgentState thiếu field 'user_query'"

test("Task 4a: Import LangGraph + AgentState", test_langgraph_imports)

def test_langgraph_nodes():
    from agent.nodes.planner import plan_steps
    from agent.nodes.retriever import retrieve_from_graph
    from agent.nodes.synthesizer import synthesize_answer
    assert callable(plan_steps), "plan_steps không phải function"
    assert callable(retrieve_from_graph), "retrieve_from_graph không phải function"
    assert callable(synthesize_answer), "synthesize_answer không phải function"

test("Task 4b: Import Agent nodes (planner, retriever, synthesizer)", test_langgraph_nodes)

def test_langgraph_graph_compile():
    from agent.graph import build_agent_graph
    compiled = build_agent_graph()
    assert compiled is not None, "Graph compile thất bại"
    # Kiểm tra graph có nodes đúng tên
    # LangGraph compiled graph có .get_graph()
    graph_repr = str(compiled.get_graph().nodes)
    assert "plan" in graph_repr, "Graph thiếu node 'plan'"
    assert "retrieve" in graph_repr, "Graph thiếu node 'retrieve'"
    assert "synthesize" in graph_repr, "Graph thiếu node 'synthesize'"

test("Task 4c: LangGraph compile thành công (Plan→Retrieve→Synthesize)", test_langgraph_graph_compile)


# ════════════════════════════════════════════════════════════
#  DATA ENGINEER — Kiểm tra
# ════════════════════════════════════════════════════════════

# Task 5: PDF Parser
def test_pdf_parser_import():
    from pipeline.ingestion.pdf_parser import parse_pdf, split_into_sections
    assert callable(parse_pdf)
    assert callable(split_into_sections)

test("Task 5a: Import PDF Parser", test_pdf_parser_import)

def test_pdf_parser_real():
    """Test parse PDF thật — dùng file đề tài."""
    from pipeline.ingestion.pdf_parser import parse_pdf, split_into_sections

    pdf_path = os.path.join(PROJECT_ROOT, "Đề tài.pdf")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError("Không tìm thấy file 'Đề tài.pdf' để test")

    result = parse_pdf(pdf_path)

    # Kiểm tra output structure
    assert "full_text" in result, "Kết quả thiếu 'full_text'"
    assert "pages" in result, "Kết quả thiếu 'pages'"
    assert "metadata" in result, "Kết quả thiếu 'metadata'"
    assert "num_pages" in result, "Kết quả thiếu 'num_pages'"

    # Kiểm tra nội dung parse được
    assert len(result["full_text"]) > 100, f"Text quá ngắn ({len(result['full_text'])} chars)"
    assert result["num_pages"] >= 1, "Không đọc được trang nào"
    assert len(result["pages"]) >= 1, "Pages list rỗng"

    # Kiểm tra split sections
    sections = split_into_sections(result["full_text"])
    assert len(sections) >= 1, "Không chia được section nào"

    print(f"       → Parse thành công: {result['num_pages']} trang, {len(result['full_text'])} chars, {len(sections)} sections")

test("Task 5b: Parse PDF thật (Đề tài.pdf)", test_pdf_parser_real)

# Task 6: Pydantic Schemas cho extraction
def test_extraction_schemas():
    from pipeline.extraction.schemas import Entity, Relation, ExtractionResult, PaperMetadata

    # Test tạo entity hợp lệ
    e = Entity(name="Transformer", type="Method", description="Self-attention model")
    assert e.name == "Transformer"

    # Test tạo relation hợp lệ
    r = Relation(source="Paper A", target="Transformer", relation="USES_METHOD", evidence="We use Transformer")
    assert r.relation == "USES_METHOD"

    # Test ExtractionResult
    result = ExtractionResult(entities=[e], relations=[r])
    assert len(result.entities) == 1
    assert len(result.relations) == 1

    # Test PaperMetadata
    meta = PaperMetadata(title="Test Paper", authors=["Author A"], year=2024)
    assert meta.title == "Test Paper"

    # Test JSON serialization (quan trọng cho việc gửi qua API)
    json_str = result.model_dump_json()
    assert "Transformer" in json_str

test("Task 6a: Pydantic Schemas (Entity, Relation, ExtractionResult)", test_extraction_schemas)

def test_extraction_prompts():
    from pipeline.extraction.prompts import EXTRACTION_PROMPT, METADATA_PROMPT
    assert len(EXTRACTION_PROMPT) > 100, "Extraction prompt quá ngắn"
    assert "CITES" in EXTRACTION_PROMPT, "Prompt thiếu relation type CITES"
    assert "USES_METHOD" in EXTRACTION_PROMPT, "Prompt thiếu USES_METHOD"
    assert "chunking" in EXTRACTION_PROMPT.lower() or "chunk" in EXTRACTION_PROMPT.lower(), \
        "Prompt không nhắc nhở KHÔNG chunking"

test("Task 6b: Prompt templates (extraction + metadata)", test_extraction_prompts)

def test_entity_extractor_import():
    from pipeline.extraction.entity_extractor import extract_entities_from_text, extract_paper_metadata
    assert callable(extract_entities_from_text)
    assert callable(extract_paper_metadata)

test("Task 6c: Import Entity Extractor functions", test_entity_extractor_import)


# ════════════════════════════════════════════════════════════
#  TỔNG KẾT
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("📊 TỔNG KẾT TUẦN 1")
print("=" * 60)

passed = sum(1 for _, status, _ in results if status == PASS)
failed = sum(1 for _, status, _ in results if status == FAIL)
total = len(results)

print(f"\n  Tổng: {total} tests")
print(f"  {PASS}: {passed}")
print(f"  {FAIL}: {failed}")

if failed > 0:
    print("\n  ⚠️ CÁC TEST FAIL:")
    for name, status, error in results:
        if status == FAIL:
            print(f"    - {name}: {error}")

print(f"\n  {'🎉 TUẦN 1 HOÀN TẤT!' if failed == 0 else '⚠️ CÒN VIỆC CẦN SỬA!'}\n")
