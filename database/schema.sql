-- CrayonStudio SQLite Database Schema

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    hook TEXT,
    category TEXT CHECK(category IN ('STEM', 'Escape/Heist', 'Architecture', 'Psychology')),
    script_text TEXT,
    duration_target INTEGER DEFAULT 65,
    tiktok_product TEXT,
    status TEXT CHECK(status IN ('Draft', 'Audio_Ready', 'Rendered', 'Ready', 'Scheduled', 'Published')) DEFAULT 'Draft',
    scheduled_time DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    source_url TEXT,
    views INTEGER DEFAULT 0,
    content_gaps TEXT,
    confusion_points TEXT,
    date_scraped DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(project_slug);
CREATE INDEX IF NOT EXISTS idx_trends_topic ON research_trends(topic);
