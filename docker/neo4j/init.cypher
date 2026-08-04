// Project Aegis-Peru - Neo4j Schema Initialization
// Ejecutar: cypher-shell -u neo4j -p <password> -f init.cypher

// ── CONSTRAINTS ─────────────────────────────────────────
CREATE CONSTRAINT investigation_case_id IF NOT EXISTS
    FOR (i:Investigation) REQUIRE i.case_id IS UNIQUE;

CREATE CONSTRAINT person_uuid IF NOT EXISTS
    FOR (p:Person) REQUIRE p.uuid IS UNIQUE;

CREATE CONSTRAINT contact_uuid IF NOT EXISTS
    FOR (c:Contact) REQUIRE c.uuid IS UNIQUE;

CREATE CONSTRAINT location_uuid IF NOT EXISTS
    FOR (l:Location) REQUIRE l.uuid IS UNIQUE;

CREATE CONSTRAINT asset_uuid IF NOT EXISTS
    FOR (a:Asset) REQUIRE a.uuid IS UNIQUE;

CREATE CONSTRAINT darkweb_uuid IF NOT EXISTS
    FOR (d:DarkWebProfile) REQUIRE d.uuid IS UNIQUE;

CREATE CONSTRAINT digital_footprint_uuid IF NOT EXISTS
    FOR (f:DigitalFootprint) REQUIRE f.uuid IS UNIQUE;

CREATE CONSTRAINT sunat_ruc IF NOT EXISTS
    FOR (s:SunatRecord) REQUIRE s.ruc IS UNIQUE;

CREATE CONSTRAINT dni_record IF NOT EXISTS
    FOR (d:DniRecord) REQUIRE d.dni IS UNIQUE;

// ── INDEXES ─────────────────────────────────────────────
CREATE INDEX person_dni_idx IF NOT EXISTS
    FOR (p:Person) ON (p.dni);

CREATE INDEX person_name_idx IF NOT EXISTS
    FOR (p:Person) ON (p.full_name);

CREATE INDEX person_risk_idx IF NOT EXISTS
    FOR (p:Person) ON (p.risk_score);

CREATE INDEX contact_value_idx IF NOT EXISTS
    FOR (c:Contact) ON (c.value);

CREATE INDEX contact_type_idx IF NOT EXISTS
    FOR (c:Contact) ON (c.contact_type);

CREATE INDEX location_coords_idx IF NOT EXISTS
    FOR (l:Location) ON (l.coordinates);

CREATE INDEX asset_hash_idx IF NOT EXISTS
    FOR (a:Asset) ON (a.hash);

CREATE INDEX darkweb_onion_idx IF NOT EXISTS
    FOR (d:DarkWebProfile) ON (d.onion_url);

CREATE INDEX investigation_status_idx IF NOT EXISTS
    FOR (i:Investigation) ON (i.status);

CREATE INDEX investigation_priority_idx IF NOT EXISTS
    FOR (i:Investigation) ON (i.priority);

// ── FULLTEXT INDEXES ────────────────────────────────────
CREATE FULLTEXT INDEX person_fulltext IF NOT EXISTS
    FOR (p:Person) ON EACH [p.full_name, p.alias];

CREATE FULLTEXT INDEX contact_fulltext IF NOT EXISTS
    FOR (c:Contact) ON EACH [c.value];

CREATE FULLTEXT INDEX investigation_fulltext IF NOT EXISTS
    FOR (i:Investigation) ON EACH [i.title, i.description];

// ── GDS PROJECTIONS (preparadas) ────────────────────────
// CALL gds.graph.project('aegis-network', ['Person', 'Contact', 'Location'], {
//     HAS_CONTACT: {orientation: 'UNDIRECTED'},
//     LOCATED_AT: {orientation: 'UNDIRECTED'},
//     LINKED_TO: {orientation: 'UNDIRECTED'}
// });

// ── STORED PROCEDURES ───────────────────────────────────
// Funcion para calcular score de riesgo
// CALL aegis.calculate_risk_score(person_uuid);

// ── SAMPLE DATA (opcional, para testing) ────────────────
// CREATE (i:Investigation {
//     case_id: 'INV-2026-001',
//     title: 'Caso de Prueba',
//     status: 'ACTIVE',
//     priority: 'CRITICAL',
//     created_at: datetime()
// });
