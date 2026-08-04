-- Project Aegis-Peru - Schema Inicial PostgreSQL
-- Ejecutado automaticamente al iniciar PostgreSQL por primera vez

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── TABLA DE USUARIOS ────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(255),
    role VARCHAR(20) NOT NULL 
        CHECK (role IN ('SUPER_ADMIN', 'CASE_OFFICER', 'ANALYST', 'AUDITOR', 'SYSTEM')),
    is_active BOOLEAN DEFAULT true,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret VARCHAR(255),
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ── TABLA DE INVESTIGACIONES ────────────────────────────
CREATE TABLE IF NOT EXISTS investigations (
    id SERIAL PRIMARY KEY,
    case_id VARCHAR(20) UNIQUE NOT NULL 
        CHECK (case_id ~ '^INV-[0-9]{4}-[0-9]{3}$'),
    title VARCHAR(300) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'ACTIVE' 
        CHECK (status IN ('ACTIVE', 'CLOSED', 'PENDING', 'ARCHIVED')),
    priority VARCHAR(20) DEFAULT 'MEDIUM' 
        CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    assigned_unit VARCHAR(100),
    lead_officer VARCHAR(100),
    classification VARCHAR(20) DEFAULT 'SECRET',
    tags TEXT[],
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ── TABLA DE EVIDENCIAS ──────────────────────────────────
CREATE TABLE IF NOT EXISTS evidences (
    id SERIAL PRIMARY KEY,
    investigation_id INTEGER REFERENCES investigations(id) ON DELETE CASCADE,
    evidence_type VARCHAR(20) NOT NULL 
        CHECK (evidence_type IN ('IMAGE', 'VIDEO', 'DOCUMENT', 'AUDIO', 'TEXT')),
    filename VARCHAR(500) NOT NULL,
    file_hash VARCHAR(128) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT NOT NULL DEFAULT 0,
    storage_path VARCHAR(500) NOT NULL,
    exif_data JSONB,
    metadata JSONB,
    uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── TABLA DE RESULTADOS OSINT ────────────────────────────
CREATE TABLE IF NOT EXISTS osint_results (
    id SERIAL PRIMARY KEY,
    investigation_id INTEGER REFERENCES investigations(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    source_type VARCHAR(20) NOT NULL 
        CHECK (source_type IN ('DNI', 'RUC', 'BREACH', 'DARKWEB', 'SOCIAL', 'SHODAN', 'CENSYS')),
    raw_data JSONB NOT NULL,
    confidence DECIMAL(3,2) CHECK (confidence >= 0 AND confidence <= 1),
    verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── TABLA DE LOGS DE AUDITORIA ──────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id VARCHAR(36),
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── TABLA DE TOKENS DE SESION (para invalidacion) ───────
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_jti VARCHAR(36) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ── INDICES ──────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_investigations_case_id ON investigations(case_id);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_investigations_priority ON investigations(priority);
CREATE INDEX IF NOT EXISTS idx_investigations_created_by ON investigations(created_by);
CREATE INDEX IF NOT EXISTS idx_evidences_investigation ON evidences(investigation_id);
CREATE INDEX IF NOT EXISTS idx_evidences_hash ON evidences(file_hash);
CREATE INDEX IF NOT EXISTS idx_osint_results_investigation ON osint_results(investigation_id);
CREATE INDEX IF NOT EXISTS idx_osint_results_source ON osint_results(source);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_jti);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- ── FUNCION PARA ACTUALIZAR updated_at ───────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ── TRIGGERS ─────────────────────────────────────────────
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_investigations_updated_at ON investigations;
CREATE TRIGGER update_investigations_updated_at
    BEFORE UPDATE ON investigations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ── USUARIO ADMIN INICIAL ───────────────────────────────
-- EN PRODUCCION: Cambiar inmediatamente con:
-- UPDATE users SET password_hash = 'nuevo_hash' WHERE username = 'admin';
-- Password por defecto: changeme-2026!
INSERT INTO users (username, password_hash, full_name, role, is_active, email)
VALUES (
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G',
    'Administrador del Sistema',
    'SUPER_ADMIN',
    true,
    'admin@aegis-peru.pnp.gob.pe'
) ON CONFLICT (username) DO NOTHING;

-- ── USUARIOS DE DEMO (solo para desarrollo) ─────────────
-- Password: changeme-2026!
INSERT INTO users (username, password_hash, full_name, role, is_active, email)
VALUES 
    ('officer1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G', 'Oficial de Caso 1', 'CASE_OFFICER', true, 'officer1@aegis-peru.pnp.gob.pe'),
    ('analyst1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G', 'Analista OSINT 1', 'ANALYST', true, 'analyst1@aegis-peru.pnp.gob.pe'),
    ('auditor1', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYA.qGZvKG6G', 'Auditor de Seguridad', 'AUDITOR', true, 'auditor1@aegis-peru.pnp.gob.pe')
ON CONFLICT (username) DO NOTHING;
