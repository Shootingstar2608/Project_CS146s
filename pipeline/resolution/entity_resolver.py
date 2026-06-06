"""
Entity Resolution — Phát hiện và gộp các entity trùng lặp trong Neo4j.

Quy trình:
  1. Lấy tất cả entity cùng loại từ Neo4j.
  2. Fuzzy matching bằng difflib.SequenceMatcher (không phụ thuộc thêm thư viện).
  3. Alias matching: kiểm tra nếu tên nằm trong aliases của entity khác.
  4. Với các cặp score > threshold nhưng chưa chắc chắn → gọi LLM xác nhận.
  5. Gộp nodes trong Neo4j: chuyển edges, merge properties, xóa node trùng.

Chạy sau mỗi lần ingest 1 paper hoặc batch.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

# Threshold cho từng loại entity (theo rubric đề bài)
_THRESHOLDS: dict[str, float] = {
    "Author": 0.85,
    "Organization": 0.90,
    "Conference": 0.90,
    "Methodology": 0.80,
    "Dataset": 0.90,
    "Topic": 0.85,
    "Task": 0.85,
}

# Threshold dưới mức này thì bỏ qua, trên mức này thì auto-merge, giữa thì LLM verify
_AUTO_MERGE_THRESHOLD = 0.95


def _fuzzy_score(a: str, b: str) -> float:
    """Case-insensitive fuzzy similarity score."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _alias_match(name_a: str, aliases_b: list[str]) -> bool:
    """Check if name_a appears in the aliases list of entity B."""
    norm_a = name_a.lower().strip()
    return any(norm_a == alias.lower().strip() for alias in aliases_b)


def _fetch_entities_by_label(label: str) -> list[dict[str, Any]]:
    """Fetch all entities of a given label from Neo4j."""
    try:
        from backend.app.core.neo4j_client import Neo4jClient

        records = Neo4jClient.execute_query(
            f"""
            MATCH (n:{label})
            RETURN n.name AS name,
                   n.description AS description,
                   COALESCE(n.aliases, []) AS aliases,
                   elementId(n) AS element_id
            """,
        )
        return records
    except Exception as exc:
        logger.warning("[ER] Failed to fetch %s entities: %s", label, exc)
        return []


def _merge_nodes_in_neo4j(
    label: str,
    keep_name: str,
    remove_name: str,
    merged_aliases: list[str],
) -> bool:
    """
    Merge two nodes: transfer all relationships from remove_node to keep_node,
    update aliases, then delete the remove_node.
    """
    try:
        from backend.app.core.neo4j_client import Neo4jClient

        # Transfer incoming relationships
        Neo4jClient.execute_write(
            f"""
            MATCH (keep:{label} {{name: $keep_name}})
            MATCH (remove:{label} {{name: $remove_name}})
            WHERE keep <> remove
            CALL {{
                WITH keep, remove
                MATCH (remove)<-[r]->(other)
                WHERE other <> keep
                WITH keep, type(r) AS rel_type, other, properties(r) AS props
                CALL apoc.create.relationship(other, rel_type, props, keep) YIELD rel
                RETURN count(rel) AS transferred
            }}
            RETURN transferred
            """,
            params={"keep_name": keep_name, "remove_name": remove_name},
        )
    except Exception:
        # APOC may not be available; use a simpler approach
        try:
            from backend.app.core.neo4j_client import Neo4jClient

            # Reconnect edges one by one using known relationship types
            for rel_type in [
                "AUTHORED", "AFFILIATED_WITH", "PUBLISHED_AT",
                "COVERS_TOPIC", "ADDRESSES_TASK", "USES_METHOD",
                "EVALUATED_ON", "CITES", "ACHIEVES", "SUBTOPIC_OF",
                "VARIANT_OF", "IMPROVES", "COMPARED_WITH",
                "RESULT_ON", "RESULT_WITH", "RELATED_TO",
            ]:
                # Outgoing edges: (remove)-[r]->(target) → (keep)-[r]->(target)
                Neo4jClient.execute_write(
                    f"""
                    MATCH (remove:{label} {{name: $remove_name}})-[r:{rel_type}]->(target)
                    MATCH (keep:{label} {{name: $keep_name}})
                    WHERE keep <> remove AND NOT (keep)-[:{rel_type}]->(target)
                    CREATE (keep)-[:{rel_type}]->(target)
                    """,
                    params={"keep_name": keep_name, "remove_name": remove_name},
                )
                # Incoming edges: (source)-[r]->(remove) → (source)-[r]->(keep)
                Neo4jClient.execute_write(
                    f"""
                    MATCH (source)-[r:{rel_type}]->(remove:{label} {{name: $remove_name}})
                    MATCH (keep:{label} {{name: $keep_name}})
                    WHERE keep <> remove AND NOT (source)-[:{rel_type}]->(keep)
                    CREATE (source)-[:{rel_type}]->(keep)
                    """,
                    params={"keep_name": keep_name, "remove_name": remove_name},
                )
        except Exception as exc:
            logger.error("[ER] Edge transfer failed for %s → %s: %s", remove_name, keep_name, exc)
            return False

    # Update aliases on the kept node
    try:
        from backend.app.core.neo4j_client import Neo4jClient

        Neo4jClient.execute_write(
            f"""
            MATCH (keep:{label} {{name: $keep_name}})
            SET keep.aliases = $aliases
            """,
            params={"keep_name": keep_name, "aliases": merged_aliases},
        )
    except Exception as exc:
        logger.debug("[ER] Alias update failed: %s", exc)

    # Delete the duplicate node and its relationships
    try:
        from backend.app.core.neo4j_client import Neo4jClient

        Neo4jClient.execute_write(
            f"""
            MATCH (remove:{label} {{name: $remove_name}})
            DETACH DELETE remove
            """,
            params={"remove_name": remove_name},
        )
    except Exception as exc:
        logger.error("[ER] Failed to delete duplicate node %r: %s", remove_name, exc)
        return False

    logger.info("[ER] Merged %s: '%s' → '%s' (aliases: %s)", label, remove_name, keep_name, merged_aliases)
    return True


def _llm_verify(entity_a: str, entity_b: str, entity_type: str, score: float) -> bool:
    """Use LLM to verify if two entities are the same."""
    try:
        from backend.app.config import get_settings
        cfg = get_settings()
        if not cfg.er_llm_verify:
            return score >= _AUTO_MERGE_THRESHOLD

        from pipeline.extraction.entity_extractor import verify_entity_resolution
        result = verify_entity_resolution(
            entity_a=entity_a,
            entity_b=entity_b,
            type_a=entity_type,
            type_b=entity_type,
            score=score,
        )
        return result.is_same
    except Exception as exc:
        logger.warning("[ER] LLM verification failed for '%s' vs '%s': %s", entity_a, entity_b, exc)
        # Fall back to score-only decision
        return score >= _AUTO_MERGE_THRESHOLD


def resolve_entities_for_label(label: str) -> dict[str, Any]:
    """
    Find and merge duplicate entities of the given label.

    Returns:
        {"label": str, "checked_pairs": int, "merged_count": int, "merges": list}
    """
    threshold = _THRESHOLDS.get(label, 0.85)
    entities = _fetch_entities_by_label(label)

    if len(entities) < 2:
        return {"label": label, "checked_pairs": 0, "merged_count": 0, "merges": []}

    # Build pairs to check
    checked_pairs = 0
    merges: list[dict[str, str]] = []
    merged_names: set[str] = set()  # track already-merged names to avoid double-merge

    for i, ent_a in enumerate(entities):
        name_a = ent_a.get("name", "")
        if not name_a or name_a in merged_names:
            continue

        for j in range(i + 1, len(entities)):
            ent_b = entities[j]
            name_b = ent_b.get("name", "")
            if not name_b or name_b in merged_names:
                continue

            checked_pairs += 1

            # Check alias match first (cheapest)
            aliases_a = ent_a.get("aliases") or []
            aliases_b = ent_b.get("aliases") or []
            is_alias = _alias_match(name_a, aliases_b) or _alias_match(name_b, aliases_a)

            # Fuzzy score
            score = _fuzzy_score(name_a, name_b)

            if score < threshold and not is_alias:
                continue

            # Decide merge
            should_merge = False
            if is_alias or score >= _AUTO_MERGE_THRESHOLD:
                should_merge = True
            elif score >= threshold:
                # Borderline — ask LLM
                should_merge = _llm_verify(name_a, name_b, label, score)

            if should_merge:
                # Keep the longer/more descriptive name as canonical
                keep = name_a if len(name_a) >= len(name_b) else name_b
                remove = name_b if keep == name_a else name_a

                # Merge aliases
                all_aliases = list(set(
                    aliases_a + aliases_b + [remove]
                ))
                # Remove the canonical name from aliases
                all_aliases = [a for a in all_aliases if a.lower().strip() != keep.lower().strip()]

                success = _merge_nodes_in_neo4j(label, keep, remove, all_aliases)
                if success:
                    merged_names.add(remove)
                    merges.append({"kept": keep, "removed": remove, "score": round(score, 3)})

    return {
        "label": label,
        "checked_pairs": checked_pairs,
        "merged_count": len(merges),
        "merges": merges,
    }


def resolve_entities_for_paper(paper_id: str | None = None) -> dict[str, Any]:
    """
    Run Entity Resolution across all entity types.

    Args:
        paper_id: Optional — currently resolves globally across all entities.
                  Future: could scope to entities connected to this paper only.

    Returns:
        {"merged_count": int, "details": list[dict]}
    """
    labels_to_resolve = [
        "Author",
        "Organization",
        "Conference",
        "Methodology",
        "Dataset",
        "Topic",
        "Task",
    ]

    total_merged = 0
    details = []

    for label in labels_to_resolve:
        result = resolve_entities_for_label(label)
        total_merged += result["merged_count"]
        if result["merged_count"] > 0:
            details.append(result)
            logger.info(
                "[ER] %s: checked %d pairs, merged %d",
                label, result["checked_pairs"], result["merged_count"],
            )

    logger.info("[ER] Total entities merged: %d", total_merged)
    return {"merged_count": total_merged, "details": details}
