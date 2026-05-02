// 03-validators.js — apply $jsonSchema validators per collection.
// Validators kept lean and aligned with packages/shared/schemas/*.json.
// Validation level: moderate (allows updates of pre-existing docs even if invalid).

db = db.getSiblingDB("solarreach");

function applyValidator(name, schema) {
  try {
    db.runCommand({
      collMod: name,
      validator: { $jsonSchema: schema },
      validationLevel: "moderate",
      validationAction: "warn",
    });
    print(`[03-validators] applied validator on ${name}`);
  } catch (e) {
    print(`[03-validators] FAILED on ${name}: ${e.message}`);
  }
}

// --- leads ---
applyValidator("leads", {
  bsonType: "object",
  required: ["_id", "client_id", "address", "postcode", "premises_type", "geo"],
  properties: {
    _id: { bsonType: "string", pattern: "^lead_" },
    client_id: { bsonType: "string" },
    address: { bsonType: "string" },
    postcode: { bsonType: "string" },
    borough: { bsonType: ["string", "null"] },
    premises_type: {
      enum: [
        "office",
        "leisure",
        "warehouse",
        "retail",
        "education",
        "residential",
        "mixed",
      ],
    },
    geo: {
      bsonType: "object",
      required: ["point"],
      properties: {
        point: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Point"] },
            coordinates: { bsonType: "array", minItems: 2, maxItems: 2 },
          },
        },
      },
    },
  },
});

// --- companies ---
applyValidator("companies", {
  bsonType: "object",
  required: ["_id", "name"],
  properties: {
    _id: { bsonType: "string", pattern: "^company_" },
    name: { bsonType: "string" },
  },
});

// --- directors ---
applyValidator("directors", {
  bsonType: "object",
  required: ["_id", "company_id", "name"],
  properties: {
    _id: { bsonType: "string", pattern: "^director_" },
    company_id: { bsonType: "string" },
    name: { bsonType: "string" },
  },
});

// --- inspire_polygons ---
applyValidator("inspire_polygons", {
  bsonType: "object",
  required: ["_id", "inspire_id", "polygon", "centroid"],
  properties: {
    _id: { bsonType: "string", pattern: "^inspire_" },
    inspire_id: { bsonType: "string" },
    polygon: {
      bsonType: "object",
      required: ["type", "coordinates"],
      properties: {
        type: { enum: ["Polygon"] },
        coordinates: { bsonType: "array" },
      },
    },
    centroid: {
      bsonType: "object",
      required: ["type", "coordinates"],
      properties: {
        type: { enum: ["Point"] },
        coordinates: { bsonType: "array", minItems: 2, maxItems: 2 },
      },
    },
  },
});

// --- clients ---
applyValidator("clients", {
  bsonType: "object",
  required: ["_id", "name"],
  properties: {
    _id: { bsonType: "string" },
    name: { bsonType: "string" },
  },
});

// --- audit_log ---
applyValidator("audit_log", {
  bsonType: "object",
  required: ["_id", "ts", "actor", "action"],
  properties: {
    _id: { bsonType: "string", pattern: "^audit_" },
    ts: { bsonType: ["string", "date"] },
    actor: { bsonType: "string" },
    action: { bsonType: "string" },
  },
});

print("[03-validators] done");
