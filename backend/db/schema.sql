-- backend/db/schema.sql
-- Run this against your local PostgreSQL database to create the schema:
--   psql amazon_purchase < backend/db/schema.sql

CREATE TABLE searches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    max_results INT DEFAULT 10,
    requirements JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending',  -- pending | scraping | confirming | analyzing | ranking | done | failed
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_id UUID REFERENCES searches(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    title TEXT,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    rating DECIMAL,
    review_count INT,
    url TEXT NOT NULL,
    image_url TEXT,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    reviewer TEXT,
    rating INT,
    title TEXT,
    body TEXT,
    helpful_votes INT DEFAULT 0,
    verified_purchase BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    summary TEXT,
    pros JSONB DEFAULT '[]',
    cons JSONB DEFAULT '[]',
    sentiment TEXT,
    score INT,   -- 0-100
    rank INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    UNIQUE(product_id)
);

CREATE TABLE price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID REFERENCES products(id) ON DELETE CASCADE,
    price DECIMAL,
    currency TEXT DEFAULT 'USD',
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
