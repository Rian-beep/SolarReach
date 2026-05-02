// 01-users.js — create app user `solarreach` with readWrite on `solarreach` db.
// Runs once on container init via /docker-entrypoint-initdb.d.

const APP_DB = "solarreach";
const APP_USER = "solarreach";
const APP_PASS = process.env.SOLARREACH_DB_PASSWORD || "solarreach_dev_password";

db = db.getSiblingDB(APP_DB);

const existing = db.getUser(APP_USER);
if (!existing) {
  db.createUser({
    user: APP_USER,
    pwd: APP_PASS,
    roles: [{ role: "readWrite", db: APP_DB }],
  });
  print(`[01-users] created user ${APP_USER} on db ${APP_DB}`);
} else {
  print(`[01-users] user ${APP_USER} already exists`);
}
