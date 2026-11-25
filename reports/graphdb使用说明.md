# GraphDB 怎么用（读 seer-all.owl）

> 一句话：GraphDB = RDF 数据库 + 自带网页工作台（Workbench）。装上后浏览器打开
> `http://localhost:7200`，建一个仓库、把 `seer-all.owl` 导进去，就能点着看实体、画关系图、
> 也能直接写 SPARQL。它按“三元组索引”设计，37 万条三元组是常规量级，不会像 Protégé 那样卡。

## 1. 拿安装包

GraphDB Free 官网下载要填注册信息，链接会发到邮箱。三条路选一条：

| 方式 | 说明 |
|---|---|
| A. 官网注册 | https://www.ontotext.com/products/graphdb/graphdb-free/ → 收邮件 → 下 **stand-alone server** 版（`graphdb-free-*-dist.zip`），不是 Desktop 版 |
| B. Maven Central | `https://repo1.maven.org/maven2/com/ontotext/graphdb/graphdb-free-runtime/` 下有 `*-dist.zip`，免注册。版本号挑最新的 |
| C. 换 Fuseki | Apache 直链、免注册，`apache-jena-fuseki-*.zip`；但只有 SPARQL 界面，没有点选浏览 |

## 2. 启动

解压到任意目录（如 `D:\graphdb`），然后：

```bat
D:\graphdb\bin\graphdb.cmd
```

等控制台出现 `Started` 后，浏览器打开 **http://localhost:7200**。
（GraphDB Free 并发限制 2 个查询，单人用完全够。）

## 3. 建仓库并导入

1. 左侧 **Setup → Repositories → Create new repository**
2. 填：
   - **Repository ID**: `seer`
   - **Ruleset**: `empty`（**推荐**，最快；我们不用它的推理，本体自己带 HermiT 一致性结果）
     - 想要 RDFS 级别的类型推断可选 `rdfs-plus`，但导入和查询都会慢一些
3. 保存后进 **Import → RDF**
4. 选 **Upload files** → 选 `seer-factor-kb\ontology\seer-all.owl`
   - 格式选 **RDF/XML**（这个文件是 OWL/XML 序列化）
   - 32 MB / 37.7 万条，导入通常 1–3 分钟
5. 导入完成会在 **Explore → Graphs overview** 看到实体分布

## 4. 常用界面

- **Explore → Class hierarchy**：按类浏览（Pet / Skill / Soulmark / Lineup / Factor）
- **Explore → Visual graph**：点一个实体，看它连出去的关系图（精灵→技能→效果）
- **SPARQL**：直接写查询，结果可存成表或导出 CSV
- 每个实体页右上角有 **Copy IRI**，配合下面的查询直接定位

## 5. 贴进去就能跑的查询

**① 看规模**

```sparql
SELECT (COUNT(*) AS ?triples) WHERE { ?s ?p ?o }
```

**② 某只精灵的技能（按威力排）**

```sparql
PREFIX seer: <http://example.org/seer#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?skill ?name ?power ?pri ?pp WHERE {
  seer:pet_4487 seer:hasSkill ?skill .
  ?skill rdfs:label ?name .
  OPTIONAL { ?skill seer:power ?power }
  OPTIONAL { ?skill seer:priority ?pri }
  OPTIONAL { ?skill seer:maxPP ?pp }
} ORDER BY DESC(?power) LIMIT 30
```

**③ 按简称找精灵（社区叫法都在 skos:altLabel）**

```sparql
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?pet ?label WHERE {
  ?pet skos:altLabel "村长"@zh .
  ?pet rdfs:label ?label
}
```

**④ 查阵容及其成员**

```sparql
PREFIX seer: <http://example.org/seer#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?lineup ?lineupName ?member ?memberName WHERE {
  ?lineup a seer:Lineup .
  ?lineup rdfs:label ?lineupName .
  ?lineup seer:lineupMember ?member .
  ?member rdfs:label ?memberName
}
```

**⑤ 魂印的 PVE 判定（人工判定优先，API 值留作溯源）**

```sparql
PREFIX seer: <http://example.org/seer#>
SELECT ?sm ?desc ?api ?verdict WHERE {
  ?sm a seer:Soulmark ; seer:desc ?desc .
  OPTIONAL { ?sm seer:pveEffective ?api }
  OPTIONAL { ?sm seer:pveVerdict ?verdict }
  FILTER(BOUND(?verdict))
}
```

**⑥ 站场技（这只精灵靠哪个技能站住）**

```sparql
PREFIX seer: <http://example.org/seer#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?petName ?skillName ?note WHERE {
  ?pet seer:sustainSkill ?skill .
  ?pet rdfs:label ?petName .
  ?skill rdfs:label ?skillName .
  OPTIONAL { ?pet seer:sustainNote ?note }
}
```

## 6. 注意

- GraphDB 是**只读展示**用，别在它里面改数据——本体的源在 `ontology/*.ttl`，改完跑
  `python seer-factor-kb/ontology/sync.py --merge-only` 重新生成 `seer-all.owl`，再重新导入。
- 导入用 `empty` ruleset 时，`a seer:Pet` 这类显式类型照常可查；只有“靠推理才成立”的隐含类型不会出现，
  我们需要的那部分在断言里都有。
- 如果导入报格式错：把 `seer-all.owl` 后缀先确认是 RDF/XML（文件头是 `<?xml ...?><rdf:RDF ...>`），
  在导入界面手动选 **RDF/XML** 而不要让 GraphDB 自动猜。