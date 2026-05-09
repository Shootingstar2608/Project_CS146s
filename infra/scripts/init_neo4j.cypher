// ─────────────────────────────────────────────────────────────────────────────
//  Neo4j Schema Initialisation — Graph-RAG Agent
//  Run automatically on first container startup via volume mount.
//  Idempotent: safe to run multiple times.
// ─────────────────────────────────────────────────────────────────────────────

// ── Constraints (enforce uniqueness + speed up MERGE) ────────────────────────
CREATE CONSTRAINT paper_name_unique    IF NOT EXISTS FOR (p:Paper)        REQUIRE p.name        IS UNIQUE;
CREATE CONSTRAINT author_name_unique   IF NOT EXISTS FOR (a:Author)       REQUIRE a.name        IS UNIQUE;
CREATE CONSTRAINT method_name_unique   IF NOT EXISTS FOR (m:Method)       REQUIRE m.name        IS UNIQUE;
CREATE CONSTRAINT metric_name_unique   IF NOT EXISTS FOR (m:Metric)       REQUIRE m.name        IS UNIQUE;
CREATE CONSTRAINT dataset_name_unique  IF NOT EXISTS FOR (d:Dataset)      REQUIRE d.name        IS UNIQUE;
CREATE CONSTRAINT task_name_unique     IF NOT EXISTS FOR (t:Task)         REQUIRE t.name        IS UNIQUE;
CREATE CONSTRAINT org_name_unique      IF NOT EXISTS FOR (o:Organization) REQUIRE o.name        IS UNIQUE;
CREATE CONSTRAINT entity_name_unique   IF NOT EXISTS FOR (e:Entity)       REQUIRE e.name        IS UNIQUE;

// ── Indexes (speed up lookup by common properties) ────────────────────────────
CREATE INDEX paper_year_idx    IF NOT EXISTS FOR (p:Paper)  ON (p.year);
CREATE INDEX paper_id_idx      IF NOT EXISTS FOR (p:Paper)  ON (p.paper_id);

// ── Seed node: confirm schema is ready ────────────────────────────────────────
MERGE (:_SchemaVersion {version: "1.0", initialized_at: datetime()});

RETURN "Neo4j schema initialised successfully." AS status;
