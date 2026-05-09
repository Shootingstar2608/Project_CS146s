"""
Pipeline: Neo4j Loader — Insert toàn bộ kết quả extraction vào Knowledge Graph.

Thiết kế:
  - Dùng Cypher MERGE (không tạo node trùng, idempotent — có thể chạy lại an toàn)
  - UNWIND để bulk insert cả list trong 1 query thay vì gọi từng node
  - Tách rõ 3 giai đoạn: constraints → nodes → edges
  - Trả về LoadResult để caller biết đã insert bao nhiêu
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from neo4j import Driver

from pipeline.extraction.schemas import (
    Entity,
    EntityType,
    ExtractionResult,
    PaperMetadata,
    Relation,
    RelationType,
    ResultEntity,
)

logger = logging.getLogger(__name__)


def _normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


# ══════════════════════════════════════════════════════════════
# RESULT TYPE
# ══════════════════════════════════════════════════════════════

@dataclass
class LoadResult:
    """Thống kê sau khi load xong 1 paper."""
    paper_id: str
    nodes_created: int = 0
    nodes_merged: int = 0       # đã tồn tại, chỉ cập nhật property
    edges_created: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


# ══════════════════════════════════════════════════════════════
# CONSTRAINTS (chạy 1 lần khi khởi động)
# ══════════════════════════════════════════════════════════════

INIT_CONSTRAINTS = """
CREATE CONSTRAINT paper_id_unique       IF NOT EXISTS FOR (n:Paper)        REQUIRE n.paper_id IS UNIQUE;
CREATE CONSTRAINT author_id_unique      IF NOT EXISTS FOR (n:Author)       REQUIRE n.author_id IS UNIQUE;
CREATE CONSTRAINT org_id_unique         IF NOT EXISTS FOR (n:Organization)  REQUIRE n.org_id IS UNIQUE;
CREATE CONSTRAINT venue_id_unique       IF NOT EXISTS FOR (n:Conference)    REQUIRE n.venue_id IS UNIQUE;
CREATE CONSTRAINT topic_id_unique       IF NOT EXISTS FOR (n:Topic)         REQUIRE n.topic_id IS UNIQUE;
CREATE CONSTRAINT method_id_unique      IF NOT EXISTS FOR (n:Methodology)   REQUIRE n.method_id IS UNIQUE;
CREATE CONSTRAINT dataset_id_unique     IF NOT EXISTS FOR (n:Dataset)       REQUIRE n.dataset_id IS UNIQUE;
CREATE CONSTRAINT result_id_unique      IF NOT EXISTS FOR (n:Result)        REQUIRE n.result_id IS UNIQUE;
"""

INIT_INDEXES = """
CREATE INDEX paper_title_idx   IF NOT EXISTS FOR (n:Paper)       ON (n.title);
CREATE INDEX paper_year_idx    IF NOT EXISTS FOR (n:Paper)       ON (n.year);
CREATE INDEX author_name_idx   IF NOT EXISTS FOR (n:Author)      ON (n.name);
CREATE INDEX method_name_idx   IF NOT EXISTS FOR (n:Methodology) ON (n.name);
CREATE INDEX dataset_name_idx  IF NOT EXISTS FOR (n:Dataset)     ON (n.name);
CREATE INDEX topic_name_idx    IF NOT EXISTS FOR (n:Topic)       ON (n.name);
CREATE INDEX venue_acronym_idx IF NOT EXISTS FOR (n:Conference)  ON (n.acronym);
"""


def init_schema(driver: Driver) -> None:
    """Tạo constraints + indexes. Gọi 1 lần khi khởi động app."""
    with driver.session() as session:
        # Neo4j chỉ cho chạy 1 statement/lần với CREATE CONSTRAINT
        for stmt in INIT_CONSTRAINTS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                session.run(stmt)
        for stmt in INIT_INDEXES.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                session.run(stmt)
    logger.info(" Neo4j schema constraints & indexes initialized")


# ══════════════════════════════════════════════════════════════
# NODE CYPHER QUERIES (MERGE — idempotent)
# ══════════════════════════════════════════════════════════════

# Mỗi entity type có Cypher riêng vì property key khác nhau
# Dùng UNWIND để bulk insert 1 query cho cả list

_MERGE_PAPER = """
UNWIND $rows AS row
MERGE (n:Paper {paper_id: row.paper_id})
ON CREATE SET
    n.name         = row.title,
    n.title        = row.title,
    n.abstract     = row.abstract,
    n.year         = row.year,
    n.doi          = row.doi,
    n.url          = row.url,
    n.pdf_path     = row.pdf_path,
    n.keywords     = row.keywords,
    n.created_at   = row.created_at
ON MATCH SET
    n.name         = COALESCE(row.title, n.name),
    n.title        = COALESCE(row.title, n.title),
    n.abstract     = COALESCE(row.abstract, n.abstract),
    n.updated_at   = row.created_at
RETURN count(n) AS total
"""

_MERGE_ENTITY_GENERIC = """
UNWIND $rows AS row
MERGE (n {name: row.name})
ON CREATE SET
    n:{label},
    n.entity_id    = row.entity_id,
    n.name         = row.name,
    n.description  = row.description,
    n.aliases      = row.aliases,
    n.created_at   = row.created_at
ON MATCH SET
    n.aliases      = [x IN (n.aliases + row.aliases) WHERE x IS NOT NULL | x],
    n.description  = COALESCE(row.description, n.description),
    n.updated_at   = row.created_at
RETURN count(n) AS total
"""

# Result cần merge riêng vì không có `name`, dùng entity_id
_MERGE_RESULT = """
UNWIND $rows AS row
MERGE (n:Result {result_id: row.result_id})
ON CREATE SET
    n.metric_name  = row.metric_name,
    n.value        = row.value,
    n.unit         = row.unit,
    n.context      = row.context,
    n.is_sota      = row.is_sota,
    n.created_at   = row.created_at
ON MATCH SET
    n.updated_at   = row.created_at
RETURN count(n) AS total
"""


# ══════════════════════════════════════════════════════════════
# EDGE CYPHER QUERIES
# ══════════════════════════════════════════════════════════════

# Template chung: match source và target theo name, MERGE edge
_MERGE_EDGE_BY_NAME = """
UNWIND $rows AS row
MATCH (src {name: row.source})
MATCH (tgt {name: row.target})
MERGE (src)-[r:{rel_type}]->(tgt)
ON CREATE SET r += row.properties, r.evidence = row.evidence, r.created_at = row.created_at
ON MATCH SET  r.evidence = COALESCE(row.evidence, r.evidence)
RETURN count(r) AS total
"""

# Paper → Result dùng paper_id + result_id (Result không có `name`)
_MERGE_ACHIEVES = """
UNWIND $rows AS row
MATCH (p:Paper {paper_id: row.paper_id})
MATCH (r:Result {result_id: row.result_id})
MERGE (p)-[rel:ACHIEVES]->(r)
ON CREATE SET rel.created_at = row.created_at
RETURN count(rel) AS total
"""


# ══════════════════════════════════════════════════════════════
# MAIN LOADER CLASS
# ══════════════════════════════════════════════════════════════

class Neo4jLoader:
    """
    Loader chính: nhận ExtractionResult + PaperMetadata → insert vào Neo4j.

    Sử dụng:
        loader = Neo4jLoader(driver)
        result = loader.load_paper(metadata, extraction)
        print(result.nodes_created, result.edges_created)
    """

    def __init__(self, driver: Driver):
        self.driver = driver

    def _build_alias_indexes(self, session) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
        """Build label-specific and global alias indexes from existing graph nodes."""
        label_indexes: dict[str, dict[str, str]] = {}
        global_index: dict[str, str] = {}

        for label in self._ENTITY_LABEL_MAP.values():
            label_index: dict[str, str] = {}
            rows = session.run(
                f"""
                MATCH (n:{label})
                RETURN coalesce(n.name, n.title, n.metric_name) AS name,
                       coalesce(n.aliases, []) AS aliases
                """
            )
            for record in rows:
                canonical = record["name"]
                if not canonical:
                    continue
                label_index[_normalize_name(canonical)] = canonical
                global_index[_normalize_name(canonical)] = canonical
                for alias in record["aliases"] or []:
                    label_index[_normalize_name(alias)] = canonical
                    global_index[_normalize_name(alias)] = canonical
            label_indexes[label] = label_index

        return label_indexes, global_index

    @staticmethod
    def _merge_aliases(existing_aliases: list[str], row_aliases: list[str], canonical: str) -> list[str]:
        merged: list[str] = []
        for value in [canonical, *existing_aliases, *row_aliases]:
            if value and value not in merged:
                merged.append(value)
        return merged

    # ──────────────────────────────────────────────
    # PUBLIC ENTRYPOINT
    # ──────────────────────────────────────────────

    def load_paper(
        self,
        metadata: PaperMetadata,
        extraction: ExtractionResult,
    ) -> LoadResult:
        """
        Insert toàn bộ 1 paper vào Neo4j. Idempotent — chạy lại không tạo duplicate.

        Args:
            metadata: Thông tin tổng quan paper (title, authors, year, venue...)
            extraction: Kết quả extraction từ LLM (entities, results, relations)

        Returns:
            LoadResult với thống kê số node/edge đã tạo
        """
        load_result = LoadResult(paper_id=metadata.paper_id)
        now = datetime.now(timezone.utc).isoformat()

        with self.driver.session() as session:
            # GIAI ĐOẠN 1: Insert Paper node chính
            self._load_paper_node(session, metadata, now, load_result)

            # GIAI ĐOẠN 2: Insert các Entity nodes
            global_index = self._load_entity_nodes(session, extraction.entities, now, load_result)

            # GIAI ĐOẠN 3: Insert Result nodes
            self._load_result_nodes(session, extraction.results, now, load_result)

            # GIAI ĐOẠN 4: Insert Edges (relations giữa entities)
            self._load_edges(session, metadata, extraction, now, load_result, global_index)

        logger.info(
            f" Loaded paper '{metadata.title}': "
            f"{load_result.nodes_created} nodes created, "
            f"{load_result.edges_created} edges created, "
            f"{len(load_result.errors)} errors"
        )
        return load_result

    # ──────────────────────────────────────────────
    # GIAI ĐOẠN 1: Paper node
    # ──────────────────────────────────────────────

    def _load_paper_node(self, session, metadata: PaperMetadata, now: str, result: LoadResult):
        try:
            session.run(_MERGE_PAPER, rows=[{
                "paper_id": metadata.paper_id,
                "title":    metadata.title,
                "abstract": metadata.abstract,
                "year":     metadata.year,
                "doi":      metadata.doi,
                "url":      "",
                "pdf_path": "",
                "keywords": metadata.keywords,
                "created_at": now,
            }])
            result.nodes_created += 1
        except Exception as e:
            msg = f"Error inserting Paper node '{metadata.title}': {e}"
            logger.error(msg)
            result.errors.append(msg)

    # ──────────────────────────────────────────────
    # GIAI ĐOẠN 2: Entity nodes
    # ──────────────────────────────────────────────

    # Map EntityType → Neo4j label (tên node trong graph)
    _ENTITY_LABEL_MAP = {
        EntityType.AUTHOR:       "Author",
        EntityType.ORGANIZATION: "Organization",
        EntityType.CONFERENCE:   "Conference",
        EntityType.TOPIC:        "Topic",
        EntityType.TASK:         "Task",         # VD: "Machine Translation", "NER"
        EntityType.METHODOLOGY:  "Methodology",
        EntityType.DATASET:      "Dataset",
        EntityType.PAPER:        "Paper",        # paper trích dẫn (stub nếu chưa upload)
    }

    def _load_entity_nodes(self, session, entities: list[Entity], now: str, result: LoadResult) -> dict[str, str]:
        label_indexes, global_index = self._build_alias_indexes(session)

        # Nhóm entities theo type để bulk insert từng nhóm, đồng thời hợp nhất alias trùng nhau
        groups: dict[str, dict[str, dict]] = {}
        for e in entities:
            label = self._ENTITY_LABEL_MAP.get(e.type)
            if label is None:
                continue  # Bỏ qua Result — xử lý riêng

            label_index = label_indexes.setdefault(label, {})
            canonical_name = label_index.get(_normalize_name(e.name))
            if canonical_name is None:
                for alias in e.aliases:
                    canonical_name = label_index.get(_normalize_name(alias))
                    if canonical_name is not None:
                        break
            if canonical_name is None:
                canonical_name = global_index.get(_normalize_name(e.name))
            if canonical_name is None:
                for alias in e.aliases:
                    canonical_name = global_index.get(_normalize_name(alias))
                    if canonical_name is not None:
                        break
            if canonical_name is None:
                canonical_name = e.name

            label_group = groups.setdefault(label, {})
            row = label_group.setdefault(canonical_name, {
                "entity_id": e.entity_id,
                "name": canonical_name,
                "description": e.description,
                "aliases": [],
                "created_at": now,
            })
            row["description"] = row["description"] or e.description
            row["aliases"] = self._merge_aliases(row["aliases"], [e.name, *e.aliases], canonical_name)

            # Update indexes so later entities in the same batch resolve to the merged canonical node.
            for alias in row["aliases"]:
                label_index[_normalize_name(alias)] = canonical_name
                global_index[_normalize_name(alias)] = canonical_name

        for label, canonical_rows in groups.items():
            try:
                # Dùng f-string để inject label vào MERGE — an toàn vì label là từ Enum
                cypher = _MERGE_ENTITY_GENERIC.replace("{label}", label)
                session.run(cypher, rows=list(canonical_rows.values()))
                result.nodes_created += len(canonical_rows)
            except Exception as e:
                msg = f"Error inserting {label} nodes (batch {len(canonical_rows)}): {e}"
                logger.error(msg)
                result.errors.append(msg)

        return global_index

    # ──────────────────────────────────────────────
    # GIAI ĐOẠN 3: Result nodes
    # ──────────────────────────────────────────────

    def _load_result_nodes(self, session, results: list[ResultEntity], now: str, result: LoadResult):
        if not results:
            return
        rows = [{
            "result_id":   r.entity_id,
            "metric_name": r.metric_name,
            "value":       r.value,
            "unit":        r.unit,
            "context":     r.context,
            "is_sota":     r.is_sota,
            "created_at":  now,
        } for r in results]

        try:
            session.run(_MERGE_RESULT, rows=rows)
            result.nodes_created += len(rows)
        except Exception as e:
            msg = f"Error inserting Result nodes: {e}"
            logger.error(msg)
            result.errors.append(msg)

    # ──────────────────────────────────────────────
    # GIAI ĐOẠN 4: Edges
    # ──────────────────────────────────────────────

    def _load_edges(
        self,
        session,
        metadata: PaperMetadata,
        extraction: ExtractionResult,
        now: str,
        result: LoadResult,
        global_index: dict[str, str] | None = None,
    ):
        if global_index is None:
            _, global_index = self._build_alias_indexes(session)

        # 4a. Relations từ LLM extraction (theo tên entity)
        # Tách riêng ACHIEVES vì Result không có `name`
        regular_relations = []
        achieves_relations = []

        for rel in extraction.relations:
            if rel.relation == RelationType.ACHIEVES:
                # Tìm result entity tương ứng theo context/metric name
                achieves_relations.append(rel)
            else:
                regular_relations.append(rel)

        # Bulk insert regular edges
        if regular_relations:
            # Nhóm theo relation type để batch insert
            rel_groups: dict[str, list[dict]] = {}
            for rel in regular_relations:
                source_name = global_index.get(_normalize_name(rel.source), rel.source)
                target_name = global_index.get(_normalize_name(rel.target), rel.target)
                rel_groups.setdefault(rel.relation.value, []).append({
                    "source":     source_name,
                    "target":     target_name,
                    "properties": rel.properties,
                    "evidence":   rel.evidence,
                    "created_at": now,
                })

            for rel_type, rows in rel_groups.items():
                try:
                    cypher = _MERGE_EDGE_BY_NAME.replace("{rel_type}", rel_type)
                    session.run(cypher, rows=rows)
                    result.edges_created += len(rows)
                except Exception as e:
                    msg = f"Error inserting {rel_type} edges: {e}"
                    logger.error(msg)
                    result.errors.append(msg)

        # 4b. Paper → Author edges (từ metadata.authors)
        self._load_author_edges(session, metadata, now, result)

        # 4c. Paper → Conference edge (từ metadata.venue)
        self._load_venue_edge(session, metadata, now, result)

        # 4d. Paper → Result (ACHIEVES) edges
        self._load_achieves_edges(session, metadata, extraction.results, now, result)

    def _load_author_edges(self, session, metadata: PaperMetadata, now: str, result: LoadResult):
        """Tạo Author nodes từ metadata + edge AUTHORED → Paper."""
        if not metadata.authors:
            return
        try:
            # Upsert Author nodes
            author_rows = [{
                "entity_id": f"author-{i}-{metadata.paper_id}",
                "name":      name,
                "description": "",
                "aliases":   [],
                "created_at": now,
            } for i, name in enumerate(metadata.authors)]

            cypher = _MERGE_ENTITY_GENERIC.replace("{label}", "Author")
            session.run(cypher, rows=author_rows)

            # Tạo AUTHORED edges
            edge_rows = [{
                "source":     name,
                "target":     metadata.title,
                "properties": {"position": i, "role": "first_author" if i == 0 else "co_author"},
                "evidence":   "",
                "created_at": now,
            } for i, name in enumerate(metadata.authors)]

            cypher = """
UNWIND $rows AS row
MATCH (src:Author {name: row.source})
MATCH (tgt:Paper {paper_id: $paper_id})
MERGE (src)-[r:AUTHORED]->(tgt)
ON CREATE SET r += row.properties, r.evidence = row.evidence, r.created_at = row.created_at
ON MATCH SET  r.evidence = COALESCE(row.evidence, r.evidence)
RETURN count(r) AS total
"""
            session.run(cypher, rows=edge_rows, paper_id=metadata.paper_id)
            result.nodes_created += len(author_rows)
            result.edges_created += len(edge_rows)
        except Exception as e:
            msg = f"Error inserting Author edges: {e}"
            logger.error(msg)
            result.errors.append(msg)

    def _load_venue_edge(self, session, metadata: PaperMetadata, now: str, result: LoadResult):
        """Tạo Conference node từ metadata.venue + edge PUBLISHED_AT."""
        if not metadata.venue:
            return
        try:
            venue_rows = [{
                "entity_id":   f"venue-{metadata.venue}",
                "name":        metadata.venue,
                "description": "",
                "aliases":     [],
                "created_at":  now,
            }]
            cypher = _MERGE_ENTITY_GENERIC.replace("{label}", "Conference")
            session.run(cypher, rows=venue_rows)

            cypher = """
MATCH (src:Paper {paper_id: $paper_id})
MATCH (tgt:Conference {name: $venue})
MERGE (src)-[rel:PUBLISHED_AT]->(tgt)
ON CREATE SET rel.created_at = $created_at
RETURN count(rel) AS total
"""
            session.run(cypher, paper_id=metadata.paper_id, venue=metadata.venue, created_at=now)
            result.nodes_created += 1
            result.edges_created += 1
        except Exception as e:
            msg = f"Error inserting Venue edge: {e}"
            logger.error(msg)
            result.errors.append(msg)

    def _load_achieves_edges(
        self,
        session,
        metadata: PaperMetadata,
        results: list[ResultEntity],
        now: str,
        result: LoadResult,
    ):
        """Tạo Paper → Result (ACHIEVES) edges dùng IDs thay vì name."""
        if not results:
            return
        try:
            rows = [{
                "paper_id":  metadata.paper_id,
                "result_id": r.entity_id,
                "created_at": now,
            } for r in results]
            session.run(_MERGE_ACHIEVES, rows=rows)
            result.edges_created += len(rows)
        except Exception as e:
            msg = f"Error inserting ACHIEVES edges: {e}"
            logger.error(msg)
            result.errors.append(msg)


# ══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ══════════════════════════════════════════════════════════════

def load_paper_to_neo4j(
    metadata: PaperMetadata,
    extraction: ExtractionResult,
    driver: Driver | None = None,
) -> LoadResult:
    """
    Shortcut function — dùng trong Celery tasks.

    Ví dụ:
        from pipeline.loader.neo4j_loader import load_paper_to_neo4j
        result = load_paper_to_neo4j(metadata, extraction)
        if result.success:
            print(f"Loaded {result.nodes_created} nodes")
    """
    if driver is None:
        from backend.app.core.neo4j_client import get_driver
        driver = get_driver()

    loader = Neo4jLoader(driver)
    return loader.load_paper(metadata, extraction)
