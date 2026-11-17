-- 赛尔号领域知识库 SQLite schema（轻量本地，零服务）
-- BOSS 特性/词条不落库：走 seerapi factor_design 实时查询
-- 反制与打法模板不落库：见 strategies.json

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tags (
  tag     TEXT PRIMARY KEY,
  meaning TEXT NOT NULL,
  layer   TEXT NOT NULL DEFAULT '机制' CHECK (layer IN ('上层','定位','机制'))
);

CREATE TABLE IF NOT EXISTS skills (
  skill_id INTEGER PRIMARY KEY,
  name     TEXT NOT NULL,
  power    INTEGER NOT NULL DEFAULT 0,
  cat      INTEGER NOT NULL DEFAULT 0,          -- 1物攻 2特攻 3属性
  type     INTEGER NOT NULL DEFAULT 0,          -- element_type_combination
  priority INTEGER NOT NULL DEFAULT 0,
  desc     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS skill_tags (
  skill_id INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
  tag      TEXT NOT NULL REFERENCES tags(tag) ON DELETE CASCADE,
  PRIMARY KEY (skill_id, tag)
);

CREATE TABLE IF NOT EXISTS pets (
  species_id     INTEGER PRIMARY KEY,
  name           TEXT NOT NULL,
  type           INTEGER NOT NULL DEFAULT 0,
  mode           TEXT NOT NULL DEFAULT 'pve' CHECK (mode IN ('pve','pvp','both')),
  aliases        TEXT NOT NULL DEFAULT '[]',     -- 外号 JSON 数组，去跳表
  role_tags      TEXT NOT NULL DEFAULT '[]',     -- 定位 JSON 数组，去跳表
  soulmark_desc  TEXT NOT NULL DEFAULT '',       -- 魂印原文（去跳表，1:1 跟随精灵）
  soulmark_tags  TEXT NOT NULL DEFAULT '[]'      -- 魂印标签 JSON 数组
);

CREATE TABLE IF NOT EXISTS pet_skills (
  species_id INTEGER NOT NULL REFERENCES pets(species_id) ON DELETE CASCADE,
  skill_id   INTEGER NOT NULL REFERENCES skills(skill_id) ON DELETE CASCADE,
  PRIMARY KEY (species_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_skill_tags_tag ON skill_tags(tag);
CREATE INDEX IF NOT EXISTS idx_pet_skills_skill ON pet_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_pets_mode ON pets(mode);