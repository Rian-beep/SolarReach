# Atlas Search & Vector Search Indexes (manual)

> Atlas Search / Vector Search indexes can NOT be created from a `mongosh` init
> script. Create them via Atlas UI / `atlas` CLI / API, or apply at runtime
> using `db.<coll>.createSearchIndex(...)` on Atlas (M10+).

Apply these against the `solarreach` database.

---

## 1. `companies_text` (Atlas Search · Lucene)

Collection: `companies`

```json
{
  "name": "companies_text",
  "type": "search",
  "definition": {
    "mappings": {
      "dynamic": false,
      "fields": {
        "name": { "type": "string", "analyzer": "lucene.english" },
        "registered_address": { "type": "string", "analyzer": "lucene.standard" },
        "ccod_proprietor_name": { "type": "string", "analyzer": "lucene.standard" }
      }
    }
  }
}
```

---

## 2. `companies_vector` (Atlas Vector Search · 1024-dim cosine)

Collection: `companies`

```json
{
  "name": "companies_vector",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine"
      }
    ]
  }
}
```

Embedding model: Voyage AI `voyage-3` (1024 dims).

---

## 3. `leads_text` (Atlas Search · Lucene)

Collection: `leads`

```json
{
  "name": "leads_text",
  "type": "search",
  "definition": {
    "mappings": {
      "dynamic": false,
      "fields": {
        "address": { "type": "string", "analyzer": "lucene.standard" },
        "postcode": { "type": "string", "analyzer": "lucene.keyword" },
        "premises_type": { "type": "string", "analyzer": "lucene.keyword" },
        "owner": {
          "type": "document",
          "fields": {
            "company_name": { "type": "string", "analyzer": "lucene.standard" }
          }
        }
      }
    }
  }
}
```

---

## 4. `calls_vector` (Atlas Vector Search on time-series)

Collection: `calls_ts`

```json
{
  "name": "calls_vector",
  "type": "vectorSearch",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "numDimensions": 1024,
        "similarity": "cosine"
      },
      {
        "type": "filter",
        "path": "lead_id"
      }
    ]
  }
}
```

Used by the Voice Agent to retrieve top-3 most-similar prior conversations
(see `THEME-NARRATIVE.md` § "How agents share context within token limits").

---

## CLI helper

For convenience, run from a connected `mongosh` session against an Atlas
M10+ cluster:

```js
db.companies.createSearchIndex({ name: "companies_text", definition: { /* see above */ } });
db.companies.createSearchIndex({ name: "companies_vector", type: "vectorSearch", definition: { /* see above */ } });
db.leads.createSearchIndex({ name: "leads_text", definition: { /* see above */ } });
db.calls_ts.createSearchIndex({ name: "calls_vector", type: "vectorSearch", definition: { /* see above */ } });
```
