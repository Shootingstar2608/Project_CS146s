from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from app.core.neo4j_client import Neo4jClient

router = APIRouter(tags=["Knowledge Graph"])

_LABEL_TO_KIND = {
    "Paper": "paper",
    "Author": "author",
    "Organization": "organization",
    "Conference": "conference",
    "Topic": "topic",
    "Task": "task",
    "Methodology": "methodology",
    "Dataset": "dataset",
    "Result": "result",
    "Year": "year",
}


def _node_kind(labels: list[str], fallback: str = "category") -> str:
    for label in labels:
        if label in _LABEL_TO_KIND:
            return _LABEL_TO_KIND[label]
    return fallback

@router.get("/graph")
def get_graph_data() -> Dict[str, List[Dict[str, Any]]]:
    """
    Truy vấn Neo4j để lấy danh sách Nodes và Links cho giao diện Graph.
    Giới hạn 200 nodes để tránh lag UI.
    """
    try:
        # Lấy tối đa 200 nodes
        nodes_query = """
        MATCH (n)
        WHERE any(label in labels(n) WHERE label IN ['Paper', 'Author', 'Organization', 'Conference', 'Topic', 'Task', 'Methodology', 'Dataset', 'Result', 'Entity'])
        RETURN id(n) AS internal_id,
               labels(n) AS labels,
               coalesce(n.name, n.title, n.metric_name, n.paper_id) AS display_name,
               coalesce(n.aliases, []) AS aliases,
               n.description AS description,
               n.paper_id AS paper_id,
               n.result_id AS result_id,
               n.year AS year
        LIMIT 200
        """
        nodes_result = Neo4jClient.execute_query(nodes_query)

        # Lấy relationships giữa các nodes đã fetch
        # Để đơn giản, lấy tối đa 500 edges
        edges_query = """
        MATCH (src)-[r]->(tgt)
        RETURN id(src) AS source, id(tgt) AS target, type(r) AS label
        LIMIT 500
        """
        edges_result = Neo4jClient.execute_query(edges_query)

        # Format lại cho Frontend
        formatted_nodes = []
        for r in nodes_result:
            labels = r.get("labels") or []
            kind = _node_kind(labels)

            formatted_nodes.append({
                "id": str(r["internal_id"]),
                "label": r.get("display_name") or r.get("paper_id") or r.get("result_id") or str(r["internal_id"]),
                "kind": kind,
                "aliases": r.get("aliases") or [],
                "description": r.get("description") or "",
                "original_id": r.get("paper_id") or r.get("result_id") or None,
            })

        formatted_links = []
        for r in edges_result:
            formatted_links.append({
                "source": str(r["source"]),
                "target": str(r["target"]),
                "label": r["label"]
            })

        return {
            "nodes": formatted_nodes,
            "links": formatted_links
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/paper/{paper_id}")
def get_graph_subgraph(paper_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Trả về subgraph quanh một Paper (1-2 hops). Dùng cho view per-paper trên frontend.
    """
    try:
        # Lấy node chính (paper) nếu có
        paper_query = """
        MATCH (p:Paper {paper_id: $paper_id})
        RETURN id(p) AS internal_id,
               labels(p) AS labels,
               coalesce(p.name, p.title, p.metric_name, p.paper_id) AS display_name,
               coalesce(p.aliases, []) AS aliases,
               p.description AS description,
               p.paper_id AS paper_id,
               p.result_id AS result_id,
               p.year AS year
        """
        paper_result = Neo4jClient.execute_query(paper_query, {"paper_id": paper_id})

        # Lấy các nodes trong vòng 2 cạnh quanh paper
        neighbors_query = """
        MATCH (p:Paper {paper_id: $paper_id})
        OPTIONAL MATCH (p)-[*1..2]-(n)
        WHERE any(label in labels(n) WHERE label IN ['Paper', 'Author', 'Organization', 'Conference', 'Topic', 'Task', 'Methodology', 'Dataset', 'Result', 'Entity'])
        RETURN DISTINCT id(n) AS internal_id,
                        labels(n) AS labels,
                        coalesce(n.name, n.title, n.metric_name, n.paper_id) AS display_name,
                        coalesce(n.aliases, []) AS aliases,
                        n.description AS description,
                        n.paper_id AS paper_id,
                        n.result_id AS result_id,
                        n.year AS year
        """
        neighbors_result = Neo4jClient.execute_query(neighbors_query, {"paper_id": paper_id})

        # Combine paper node and neighbor nodes, deduplicate by internal_id
        combined = { }
        for r in paper_result + neighbors_result:
            iid = r["internal_id"]
            combined[iid] = r

        node_ids = [int(k) for k in combined.keys()]

        # Lấy các cạnh giữa các node đã chọn
        links = []
        if node_ids:
            edges_query = """
            MATCH (src)-[r]-(tgt)
            WHERE id(src) IN $ids AND id(tgt) IN $ids
            RETURN id(src) AS source, id(tgt) AS target, type(r) AS label
            LIMIT 1000
            """
            edges_result = Neo4jClient.execute_query(edges_query, {"ids": node_ids})
        else:
            edges_result = []

        # Format nodes and edges
        formatted_nodes = []
        for r in combined.values():
            labels = r.get("labels") or []
            kind = _node_kind(labels)

            formatted_nodes.append({
                "id": str(r["internal_id"]),
                "label": r.get("display_name") or r.get("paper_id") or r.get("result_id") or str(r["internal_id"]),
                "kind": kind,
                "aliases": r.get("aliases") or [],
                "description": r.get("description") or "",
                "original_id": r.get("paper_id") or r.get("result_id") or None,
            })

        formatted_links = []
        for r in edges_result:
            formatted_links.append({
                "source": str(r["source"]),
                "target": str(r["target"]),
                "label": r["label"]
            })

        return {"nodes": formatted_nodes, "links": formatted_links}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
