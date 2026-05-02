// 02-collections.js — create all collections incl. 3 time-series.
// Idempotent: check listCollectionNames() first.

db = db.getSiblingDB("solarreach");

const STANDARD = [
  "leads",
  "companies",
  "directors",
  "inspire_polygons",
  "clients",
  "audit_log",
  "agent_registry",
  "outreach_variants",
  "webhooks_inbox",
];

const existing = new Set(db.getCollectionNames());

for (const name of STANDARD) {
  if (!existing.has(name)) {
    db.createCollection(name);
    print(`[02-collections] created ${name}`);
  } else {
    print(`[02-collections] skip ${name} (exists)`);
  }
}

// Time-series collections — see CONTRACTS § 1.
const TS_DEFS = [
  {
    name: "calls_ts",
    timeField: "ts",
    metaField: "lead_id",
    granularity: "seconds",
  },
  {
    name: "energy_yield_ts",
    timeField: "ts",
    metaField: "building_id",
    granularity: "hours",
  },
  {
    name: "weather_ts",
    timeField: "ts",
    metaField: "cell_id",
    granularity: "hours",
  },
];

for (const ts of TS_DEFS) {
  if (!existing.has(ts.name)) {
    db.createCollection(ts.name, {
      timeseries: {
        timeField: ts.timeField,
        metaField: ts.metaField,
        granularity: ts.granularity,
      },
    });
    print(`[02-collections] created time-series ${ts.name}`);
  } else {
    print(`[02-collections] skip ${ts.name} (exists)`);
  }
}

print("[02-collections] done");
