# LifeLink NE JSON API (for the native mobile app)

Base URL: `http://<your-server>/api/v1`

Auth: opaque bearer tokens (not JWT). Register or log in to get a
`token`, then send it as a header on every other request:

```
Authorization: Bearer <token>
```

All request/response bodies are JSON (`Content-Type: application/json`)
except the QR PNG endpoint.

---

## Reference data

### `GET /meta`  (no auth required)
Returns the pickers your registration/report screens need, so the app
never has to hardcode the NE state list, location list, disaster
catalog, or blood groups.

```json
{
  "ne_states": ["Arunachal Pradesh", "Assam", ...],
  "locations": [{"label": "Guwahati (Assam)", "lat": 26.1445, "lon": 91.7362}, ...],
  "blood_groups": ["A+", "A-", ...],
  "disaster_catalog": {
    "Severe": ["Major Flood", "Flash Flood", "Earthquake", ...],
    "Moderate": ["Flood", "Waterlogging", ...],
    "Mild": ["Localized Waterlogging", "Lightning Strike", ...]
  },
  "map_center": {"lat": 26.3, "lon": 92.5},
  "map_default_zoom": 7
}
```

---

## Auth

### `POST /auth/register`
```json
{
  "username": "Priya Sharma",
  "email": "priya@example.com",
  "password": "Passw0rd!",
  "birthday": "1995-05-05",
  "home_location": "Guwahati (Assam)",   // must be a label from GET /meta
  "exact_location": "26.15, 91.73",      // optional, "lat, lon" from device GPS
  "blood_group": "O+",
  "disabilities": "", "diseases": "", "allergies": "", "important_contacts": ""
}
```
→ `201` `{ "token": "...", "user": {...} }`
→ `400` `{ "errors": ["..."] }`

Password rule: 8+ characters, at least one digit and one symbol
(`!@#$%^&*`).

Self-registration only ever creates a regular account. Admin and health
worker roles are granted out-of-band by whoever runs the server
(`make_admin.py` / `make_health_worker.py`), never through this endpoint.

### `POST /auth/login`
```json
{ "email": "priya@example.com", "password": "Passw0rd!" }
```
→ `200` `{ "token": "...", "user": {...} }`
→ `401` `{ "error": "Incorrect email or password." }`

### `POST /auth/logout`  (auth required)
Invalidates just the token used on this request (i.e. logs out this
device only). → `204`

### `POST /auth/logout-all`  (auth required)
Invalidates every token for this user (log out all devices). → `204`

---

## Profile

### `GET /me`  (auth required)
Returns the current user.

### `PATCH /me`  (auth required)
Send only the fields you want to change:
```json
{ "diseases": "Asthma", "important_contacts": "Mother: +91..." }
```
→ `200` full updated user object.

User object shape:
```json
{
  "user_id": "...", "username": "...", "email": "...",
  "birthday": "...", "disabilities": "...",
  "home_location": {"raw": "26.14, 91.73", "lat": 26.14, "lon": 91.73, "label": "Guwahati (Assam)"},
  "exact_location": {...same shape...},
  "is_admin": false,
  "is_health_worker": false,
  "blood_group": "...", "diseases": "...", "allergies": "...",
  "important_contacts": "...", "created_at": "..."
}
```

---

## Disaster reports

### `GET /disasters`  (auth required)
→ `{ "disasters": [ {...}, ... ] }`, newest first.

Disaster object shape:
```json
{
  "disaster_id": "...",
  "reporter_name": "...",
  "location": {"raw": "...", "lat": 26.15, "lon": 91.73, "label": "..."},
  "disaster": "Major Flood",
  "severity": "Severe",
  "severity_color": "#e74c3c",
  "notes": "...",
  "reported_at": "2026-08-07T07:05:27+00:00",
  "can_delete": true
}
```

### `POST /disasters`  (auth required)
```json
{ "disaster": "Major Flood", "notes": "Embankment breach near village", "lat": 26.15, "lon": 91.73 }
```
`severity` is optional — omit it and the server derives it from the
disaster type using the catalog in `GET /meta`. `lat`/`lon` are also
optional — omit them and the server falls back to the user's saved
`exact_location`. → `201` the created disaster object.

### `DELETE /disasters/<disaster_id>`  (auth required, owner or admin only)
→ `204`, or `403` if you don't own the report.

### `POST /disasters/clear`  (admin only)
Wipes all disaster reports. → `204`, or `403` if not an admin.

### `GET /disasters/map`  (auth required)
Data for the intensity map screen:
```json
{
  "heat_points": [[26.15, 91.73, 4], ...],   // [lat, lon, weight]
  "hotspots": [
    {"lat": 26.15, "lon": 91.73, "count": 8, "max_severity": "Severe", "color": "#e74c3c", "label": "..."}
  ],
  "total_reports": 91,
  "map_center": {"lat": 26.3, "lon": 92.5},
  "map_default_zoom": 7
}
```
Feed `heat_points` straight into a native heatmap layer. Weight is 1 for
Mild, 2 for Moderate, 4 for Severe.

---

## Blood donation network

There is intentionally no blood *request* endpoint — this is a donor
directory only. People sign up as available donors and are found
directly by location/blood type.

### `GET /blood/donations`  (auth required)
→ `{ "donations": [ {...}, ... ] }`, newest first.

Donation object shape:
```json
{
  "id": "...",
  "name": "...",
  "location": {"raw": "...", "lat": 26.15, "lon": 91.73, "label": "..."},
  "blood_type": "O+",
  "contact": "...",
  "created_at": "...",
  "can_delete": true
}
```

### `POST /blood/donations`  (auth required)
```json
{ "name": "Priya Sharma", "blood_type": "O+", "contact": "+91...", "lat": 26.15, "lon": 91.73 }
```
`lat`/`lon` optional, falls back to `exact_location`. → `201` the created
donation object.

### `DELETE /blood/donations/<id>`  (auth required, owner or admin only)
→ `204`, or `403` if you don't own the entry.

### `POST /blood/donations/clear`  (admin only)
Wipes all donor entries. → `204`, or `403` if not an admin.

---

## Health records (health worker / admin only)

### `GET /health-records?q=<name>`  (health worker or admin required)
Case-insensitive substring search on username. Returns only the health
fields — no email, location, or account metadata.

```json
{
  "results": [
    {
      "user_id": "...",
      "username": "Priya Sharma",
      "birthday": "1995-05-05",
      "blood_group": "O+",
      "disabilities": "",
      "diseases": "Asthma",
      "allergies": "Penicillin",
      "important_contacts": "Mother: +91..."
    }
  ]
}
```
→ `403 { "error": "Health worker privileges required." }` if the caller
isn't a health worker or admin.

---

## Emergency passport

### `GET /me/passport`  (auth required)
```json
{ "payload": "Name: ...\nBirthday: ...\n..." }
```
Use this if you want to render the QR code natively on-device (sharper
on high-DPI screens).

### `GET /me/qr`  (auth required)
Returns a ready-made PNG (`image/png`) if you'd rather just display an
image than generate the QR code yourself.

---

## Errors

- `401 { "error": "Missing or invalid API token." }` — bad/missing/expired token.
- `403 { "error": "..." }` — authenticated, but not allowed to do this.
- `404 { "error": "Not found." }`
- `400 { "errors": ["...", "..."] }` — validation failures (note: plural `errors`, an array).

The web app (browser, session-cookie based) and this API are
completely independent auth-wise but share the same database — a
disaster reported from the app shows up on the website instantly, and
vice versa.
