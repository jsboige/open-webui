-- ============================================================================
-- Open WebUI Multi-Tenant PostgreSQL Initialization
-- ============================================================================
-- This script creates one database per tenant for complete isolation.
-- Run automatically on first startup via docker-entrypoint-initdb.d
--
-- Databases created:
--   - myia_db      (primary tenant)
--   - epf_db       (student tenant)
--   - epf_genai_db (student tenant)
--   - ece_db       (student tenant)
--   - esg_db       (student tenant)
--   - epita_db     (student tenant)
--   - pauwels_db   (student tenant)
--
-- Each tenant's Open WebUI instance will:
--   1. Connect to its dedicated database
--   2. Run Alembic migrations to create tables
--   3. Optionally migrate existing SQLite data
-- ============================================================================

-- Set client encoding
SET client_encoding = 'UTF8';

-- Create databases for each tenant
-- Note: The openwebui user is created automatically by POSTGRES_USER

-- Primary tenant: myia
CREATE DATABASE myia_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

-- Student tenants
CREATE DATABASE epf_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

CREATE DATABASE epf_genai_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

CREATE DATABASE ece_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

CREATE DATABASE esg_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

CREATE DATABASE epita_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

CREATE DATABASE pauwels_db
    OWNER openwebui
    ENCODING 'UTF8'
    LC_COLLATE = 'C'
    LC_CTYPE = 'C'
    TEMPLATE template0;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE myia_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE epf_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE epf_genai_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE ece_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE esg_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE epita_db TO openwebui;
GRANT ALL PRIVILEGES ON DATABASE pauwels_db TO openwebui;

-- Log creation
DO $$
BEGIN
    RAISE NOTICE 'Open WebUI databases created successfully:';
    RAISE NOTICE '  - myia_db';
    RAISE NOTICE '  - epf_db';
    RAISE NOTICE '  - epf_genai_db';
    RAISE NOTICE '  - ece_db';
    RAISE NOTICE '  - esg_db';
    RAISE NOTICE '  - epita_db';
    RAISE NOTICE '  - pauwels_db';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Start each tenant with DATABASE_URL set to its database';
    RAISE NOTICE '  2. Let Alembic create the tables';
    RAISE NOTICE '  3. Migrate data using open-webui-postgres-migration tool';
END $$;
