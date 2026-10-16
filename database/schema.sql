-- CrayonStudio SQLite Database Schema

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    hook TEXT DEFAULT '',
    category TEXT CHECK(category IN ('STEM', 'How It''s Made', 'Engineering', 'Escape/Heist', 'Architecture', 'Psychology')) DEFAULT 'STEM',
    visual_engine TEXT DEFAULT '3D_Pixar',
    render_mode TEXT DEFAULT 'smart_hybrid',
    script_text TEXT DEFAULT '',
    duration_target INTEGER DEFAULT 65,
    tiktok_product TEXT DEFAULT '',
    style_reference_path TEXT DEFAULT '',
    meta_title TEXT DEFAULT '',
    meta_description TEXT DEFAULT '',
    meta_hashtags TEXT DEFAULT '#stem #satisfying #engineering #learnontiktok',
    storyboard_json TEXT DEFAULT '[]',
    status TEXT CHECK(status IN ('Draft', 'Audio_Ready', 'Rendered', 'Ready', 'Scheduled', 'Published')) DEFAULT 'Draft',
    scheduled_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    source_url TEXT,
    views INTEGER DEFAULT 0,
    confusion_points TEXT,
    complaints TEXT,
    praises TEXT,
    content_gaps TEXT,
    date_scraped DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(project_slug);
CREATE INDEX IF NOT EXISTS idx_trends_topic ON research_trends(topic);

CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    images_generated INTEGER DEFAULT 0,
    video_seconds REAL DEFAULT 0.0,
    estimated_cost_usd REAL DEFAULT 0.0,
    status TEXT DEFAULT 'ok',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_logs(created_at);

