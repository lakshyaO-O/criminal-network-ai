-- Migration: 001_initial_schema.sql
-- Canonical data model for SIH 26189 AI-Powered Criminal Network Analysis System
-- Aligned with ai/schemas.py and docs/data-model.md (single source of truth).
--
-- ID CONTRACT: IDs are TEXT, format {prefix}-{5 digits} (e.g. person-00042,
-- rel-00117), assigned by the application for idempotent upserts.
-- They are NOT UUIDs. CHECK constraints enforce prefix + format.
-- In the relational store, <type>_id IS the entity_id used by the graph layer.
--
-- NOT for real PII; synthetic data only.
-- SAFETY: investigator-assistance system; no guilt/criminality labels stored.

-- ============================================================
-- ENUM TYPES
-- ============================================================

-- Entity types
CREATE TYPE entity_type AS ENUM (
    'Person',
    'Organization',
    'PhoneNumber',
    'Vehicle',
    'Location',
    'FinancialAccount',
    'Transaction',
    'Communication',
    'Case',
    'FIR',
    'Event',
    'Evidence'
);

-- Relationship types (canonical set of 11)
CREATE TYPE relationship_type AS ENUM (
    'KNOWS',
    'CALLED',
    'TRANSFERRED_TO',
    'LOCATED_AT',
    'TRAVELED_TO',
    'ASSOCIATED_WITH',
    'WORKS_FOR',
    'OWNS',
    'USED',
    'MENTIONED_IN',
    'RELATED_TO_CASE'
);

CREATE TYPE case_status AS ENUM ('open', 'under_investigation', 'closed');
CREATE TYPE fir_type AS ENUM ('FIR', 'complaint', 'intel_report');
CREATE TYPE evidence_status AS ENUM ('logged', 'in_custody', 'under_review');

-- ============================================================
-- CORE ENTITY TABLES
-- ============================================================

-- Person table
CREATE TABLE persons (
    person_id TEXT PRIMARY KEY
        CHECK (person_id ~ '^person-[0-9]{5}$'),
    full_name VARCHAR(200) NOT NULL,
    date_of_birth DATE,
    nationality VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Organization table
CREATE TABLE organizations (
    org_id TEXT PRIMARY KEY
        CHECK (org_id ~ '^org-[0-9]{5}$'),
    name VARCHAR(200) NOT NULL,
    org_type VARCHAR(100),
    registration_number VARCHAR(50),
    jurisdiction VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- PhoneNumber table
CREATE TABLE phone_numbers (
    phone_id TEXT PRIMARY KEY
        CHECK (phone_id ~ '^phone-[0-9]{5}$'),
    number VARCHAR(20) NOT NULL,       -- E.164-style, fictional ranges only
    phone_type VARCHAR(20),            -- mobile / landline / fax
    carrier VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vehicle table
CREATE TABLE vehicles (
    vehicle_id TEXT PRIMARY KEY
        CHECK (vehicle_id ~ '^vehicle-[0-9]{5}$'),
    registration_number VARCHAR(20) NOT NULL,
    make VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    color VARCHAR(30),
    vin VARCHAR(30),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Location table
CREATE TABLE locations (
    location_id TEXT PRIMARY KEY
        CHECK (location_id ~ '^location-[0-9]{5}$'),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    description VARCHAR(255),
    area_name VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- FinancialAccount table
CREATE TABLE financial_accounts (
    account_id TEXT PRIMARY KEY
        CHECK (account_id ~ '^account-[0-9]{5}$'),
    account_number VARCHAR(30) NOT NULL,   -- fictional, masked in UIs
    account_type VARCHAR(30),
    institution VARCHAR(200),
    jurisdiction VARCHAR(100),
    currency VARCHAR(10),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Transaction table (event-like)
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY
        CHECK (transaction_id ~ '^transaction-[0-9]{5}$'),
    amount DECIMAL(15,2) NOT NULL,
    transaction_type VARCHAR(30) NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR',
    from_account_id TEXT REFERENCES financial_accounts(account_id),
    to_account_id TEXT REFERENCES financial_accounts(account_id),
    timestamp TIMESTAMP NOT NULL,
    is_flagged_demo BOOLEAN DEFAULT FALSE,  -- demo anomaly marker only
    description TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Communication table (event-like; polymorphic endpoints)
CREATE TABLE communications (
    comm_id TEXT PRIMARY KEY
        CHECK (comm_id ~ '^comm-[0-9]{5}$'),
    medium VARCHAR(30) NOT NULL,       -- call / sms / email / chat
    direction VARCHAR(10) NOT NULL,    -- incoming / outgoing
    from_entity_type entity_type NOT NULL,
    from_entity_id TEXT NOT NULL,
    to_entity_type entity_type NOT NULL,
    to_entity_id TEXT NOT NULL,
    from_phone_id TEXT REFERENCES phone_numbers(phone_id),
    to_phone_id TEXT REFERENCES phone_numbers(phone_id),
    timestamp TIMESTAMP NOT NULL,
    duration_seconds INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Case table
CREATE TABLE cases (
    case_id TEXT PRIMARY KEY
        CHECK (case_id ~ '^case-[0-9]{5}$'),
    case_number VARCHAR(50) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    case_type VARCHAR(100),
    status case_status DEFAULT 'open',
    assigned_to TEXT REFERENCES persons(person_id),
    opened_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- FIR/Report table
CREATE TABLE firs (
    fir_id TEXT PRIMARY KEY
        CHECK (fir_id ~ '^fir-[0-9]{5}$'),
    fir_number VARCHAR(50) NOT NULL UNIQUE,
    case_id TEXT REFERENCES cases(case_id),
    fir_type fir_type NOT NULL,
    filed_at TIMESTAMP NOT NULL,
    filed_by TEXT REFERENCES persons(person_id),
    jurisdiction VARCHAR(100),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Event table (observed activity)
CREATE TABLE events (
    event_id TEXT PRIMARY KEY
        CHECK (event_id ~ '^event-[0-9]{5}$'),
    name VARCHAR(200),
    description TEXT,
    event_type VARCHAR(100),           -- meeting / sighting / handoff / travel
    timestamp TIMESTAMP NOT NULL,
    location_id TEXT REFERENCES locations(location_id),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Evidence table (metadata only — never raw content)
CREATE TABLE evidence (
    evidence_id TEXT PRIMARY KEY
        CHECK (evidence_id ~ '^evidence-[0-9]{5}$'),
    case_id TEXT REFERENCES cases(case_id),
    description TEXT,
    evidence_type VARCHAR(50),
    source VARCHAR(200),
    collected_at TIMESTAMP NOT NULL,
    collected_by TEXT REFERENCES persons(person_id),
    chain_hash TEXT,                   -- populated by blockchain module later
    status evidence_status DEFAULT 'logged',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- RELATIONSHIP TABLE (canonical relationship store)
-- ============================================================

-- Canonical relationships with FULL PROVENANCE.
-- Endpoints are polymorphic, so FK constraints cannot apply; integrity is
-- enforced by application validation (ai.schemas) and the test suite.
CREATE TABLE relationships (
    relationship_id TEXT PRIMARY KEY
        CHECK (relationship_id ~ '^rel-[0-9]{5}$'),
    source_id TEXT NOT NULL,
    source_type entity_type NOT NULL,
    target_id TEXT NOT NULL,
    target_type entity_type NOT NULL,
    relationship_type relationship_type NOT NULL,
    timestamp TIMESTAMP,               -- event time if available, else NULL
    confidence REAL NOT NULL
        CHECK (confidence >= 0 AND confidence <= 1),
    extraction_method VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    -- Self-loops are forbidden by the canonical model
    CONSTRAINT no_self_loop CHECK (
        NOT (source_id = target_id AND source_type = target_type)
    )
);

-- ============================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ============================================================

-- Entity lookup indexes
CREATE INDEX idx_persons_full_name ON persons(full_name);
CREATE INDEX idx_organizations_name ON organizations(name);
CREATE INDEX idx_locations_geo ON locations(latitude, longitude);
CREATE INDEX idx_phone_numbers_number ON phone_numbers(number);

-- Relationship indexes
CREATE INDEX idx_relationships_source ON relationships(source_id, source_type);
CREATE INDEX idx_relationships_target ON relationships(target_id, target_type);
CREATE INDEX idx_relationships_type ON relationships(relationship_type);
CREATE INDEX idx_relationships_timestamp ON relationships(timestamp);
CREATE INDEX idx_relationships_confidence ON relationships(confidence);

-- Case/FIR indexes
CREATE INDEX idx_cases_number ON cases(case_number);
CREATE INDEX idx_firs_number ON firs(fir_number);
CREATE INDEX idx_firs_case ON firs(case_id);

-- Communication indexes
CREATE INDEX idx_communications_timestamp ON communications(timestamp);
CREATE INDEX idx_communications_from ON communications(from_entity_id, from_entity_type);
CREATE INDEX idx_communications_to ON communications(to_entity_id, to_entity_type);

-- Transaction indexes
CREATE INDEX idx_transactions_from_account ON transactions(from_account_id);
CREATE INDEX idx_transactions_to_account ON transactions(to_account_id);
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);

-- Evidence indexes
CREATE INDEX idx_evidence_case ON evidence(case_id);
CREATE INDEX idx_evidence_status ON evidence(status);

-- Event indexes
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_location ON events(location_id);
