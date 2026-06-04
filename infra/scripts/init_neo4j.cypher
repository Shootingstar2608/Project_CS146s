// ─────────────────────────────────────────────────────────────────────────────
//  Neo4j Schema Initialisation — Graph-RAG Agent
//  Run automatically on first container startup via volume mount.
//  Idempotent: safe to run multiple times.
// ─────────────────────────────────────────────────────────────────────────────

// ── Constraints (enforce uniqueness + speed up MERGE) ────────────────────────
CREATE CONSTRAINT paper_id_unique      IF NOT EXISTS FOR (p:Paper)        REQUIRE p.paper_id    IS UNIQUE;
CREATE CONSTRAINT author_name_unique   IF NOT EXISTS FOR (a:Author)       REQUIRE a.name        IS UNIQUE;
CREATE CONSTRAINT org_name_unique      IF NOT EXISTS FOR (o:Organization) REQUIRE o.name        IS UNIQUE;
CREATE CONSTRAINT conference_name_unique IF NOT EXISTS FOR (c:Conference) REQUIRE c.name        IS UNIQUE;
CREATE CONSTRAINT topic_name_unique    IF NOT EXISTS FOR (t:Topic)        REQUIRE t.name        IS UNIQUE;
CREATE CONSTRAINT task_name_unique     IF NOT EXISTS FOR (t:Task)         REQUIRE t.name        IS UNIQUE;
CREATE CONSTRAINT methodology_name_unique IF NOT EXISTS FOR (m:Methodology) REQUIRE m.name      IS UNIQUE;
CREATE CONSTRAINT dataset_name_unique  IF NOT EXISTS FOR (d:Dataset)      REQUIRE d.name        IS UNIQUE;
CREATE CONSTRAINT result_id_unique     IF NOT EXISTS FOR (r:Result)       REQUIRE r.result_id   IS UNIQUE;

// ── Indexes (speed up lookup by common properties) ────────────────────────────
CREATE INDEX paper_year_idx    IF NOT EXISTS FOR (p:Paper)  ON (p.year);
CREATE INDEX paper_title_idx   IF NOT EXISTS FOR (p:Paper)  ON (p.title);

// ── Seed node: confirm schema is ready ────────────────────────────────────────
MERGE (:_SchemaVersion {version: "1.0", initialized_at: datetime()});

RETURN "Neo4j schema initialised successfully." AS status;
