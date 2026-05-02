// 04-indexes.js — geo (2dsphere), compound, single-field indexes per CONTRACTS § 1.

db = db.getSiblingDB("solarreach");

function ix(coll, spec, opts) {
  try {
    db.getCollection(coll).createIndex(spec, opts || {});
    print(`[04-indexes] ${coll} ${JSON.stringify(spec)}`);
  } catch (e) {
    print(`[04-indexes] FAILED ${coll} ${JSON.stringify(spec)}: ${e.message}`);
  }
}

// --- leads ---
ix("leads", { "geo.point": "2dsphere" });
ix("leads", { client_id: 1, "scores.composite_score": -1 });
ix("leads", { postcode: 1 });
ix("leads", { "owner.company_id": 1 });

// --- companies ---
ix("companies", { ccod_proprietor_name: 1 });
ix("companies", { title_number: 1 });

// --- directors ---
ix("directors", { company_id: 1 });
ix("directors", { ch_officer_id: 1 }, { sparse: true });

// --- inspire_polygons ---
ix("inspire_polygons", { polygon: "2dsphere" });
ix("inspire_polygons", { centroid: "2dsphere" });
ix("inspire_polygons", { inspire_id: 1 }, { unique: true });
ix("inspire_polygons", { borough: 1 });

// --- audit_log ---
ix("audit_log", { ts: -1 });
ix("audit_log", { actor: 1, ts: -1 });
ix("audit_log", { lead_id: 1, ts: -1 }, { sparse: true });

// --- agent_registry ---
ix("agent_registry", { skills: 1 });

// --- outreach_variants ---
ix("outreach_variants", { lead_id: 1 });

// --- webhooks_inbox ---
ix("webhooks_inbox", { received_at: -1 });

print("[04-indexes] done");
