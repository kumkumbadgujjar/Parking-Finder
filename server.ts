import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import express from 'express';
import { createServer as createViteServer } from 'vite';

interface UserRecord {
  username: string;
  password: string;
  email?: string;
}

export interface RealParkingSpot {
  id: string;
  placeId: string;
  name: string;
  address: string;
  lat: number;
  lon: number;
  distanceKm: number;
  directionsUri: string;
  dataSource: string;
  availabilityStatus: string;
}

const USERS_FILE = path.resolve(process.cwd(), 'users.json');
const USER_AGENT = 'SmartParkingFinder/2.0';
const SOLUTION_ID = 'gmp_mcp_codeassist_v1_aistudio';
const OVERPASS_ENDPOINTS = [
  'https://overpass-api.de/api/interpreter',
  'https://overpass.kumi.systems/api/interpreter',
  'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
];

function getGoogleApiKey(): string {
  return (process.env.GOOGLE_MAPS_API_KEY ?? '').trim();
}

function loadUsers(): UserRecord[] {
  try {
    const raw = fs.readFileSync(USERS_FILE, 'utf-8');
    const parsed = JSON.parse(raw) as { users?: UserRecord[] };
    if (Array.isArray(parsed.users)) {
      return parsed.users;
    }
  } catch {
    // Fallback to initial seeded accounts if file unreadable
  }
  return [
    { username: 'kumkum', password: '1234', email: 'kumkum@parkingfinder.local' },
    {
      username: 'mahek',
      password: '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4',
      email: 'kumkumbadgujjar@gmail.com',
    },
    {
      username: 'cse24',
      password: '205e9495af4a71f334be95c5484c10ea7535948050ba99d236713058a3661d23',
      email: 'cse24@gmail.com',
    },
    {
      username: 'Anmol00',
      password: 'd385077fb4b9bf9ac46484e8b47bc3ccc90e9fbea778085c00d4abe688b0db79',
      email: 'rajbadgujjar@gmail.com',
    },
  ];
}

function saveUsers(users: UserRecord[]): void {
  try {
    fs.writeFileSync(USERS_FILE, JSON.stringify({ users }, null, 2), 'utf-8');
  } catch {
    // Ignore write failure on read-only environments
  }
}

function hashPassword(password: string): string {
  return crypto.createHash('sha256').update(password).digest('hex');
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dlat = toRad(lat2 - lat1);
  const dlon = toRad(lon2 - lon1);
  const a =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlon / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

async function geocodeEnglish(query: string): Promise<{
  lat: number;
  lon: number;
  displayName: string;
  method: string;
}> {
  const cleaned = query.trim();
  const apiKey = getGoogleApiKey();

  if (apiKey) {
    const url = new URL(
      `https://geocode.googleapis.com/v4/geocode/address/${encodeURIComponent(cleaned)}`
    );
    url.searchParams.set('languageCode', 'en');
    url.searchParams.set('regionCode', 'IN');

    const res = await fetch(url.toString(), {
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': apiKey,
        'X-Goog-FieldMask': 'results.placeId,results.location,results.formattedAddress',
        'X-Goog-Maps-Solution-ID': SOLUTION_ID,
      },
      signal: AbortSignal.timeout(8000),
    });

    const data = (await res.json()) as {
      results?: Array<{
        formattedAddress?: string;
        location?: { latitude: number; longitude: number };
      }>;
      error?: { status?: string; message?: string };
    };

    if (!res.ok) {
      throw new Error(
        `Google Geocoding API error (${data.error?.status ?? res.status}): ${
          data.error?.message ?? 'Request failed'
        }`
      );
    }

    const first = data.results?.[0];
    if (!first?.location) {
      throw new Error(`ZERO_RESULTS: Could not find '${cleaned}'.`);
    }

    return {
      lat: first.location.latitude,
      lon: first.location.longitude,
      displayName: first.formattedAddress || cleaned,
      method: 'Google Geocoding API (English)',
    };
  }

  // English-forced Nominatim geocoding when no Google API key is configured in container
  const url = new URL('https://nominatim.openstreetmap.org/search');
  url.searchParams.set('q', cleaned);
  url.searchParams.set('format', 'json');
  url.searchParams.set('accept-language', 'en');
  url.searchParams.set('limit', '1');

  const res = await fetch(url.toString(), {
    headers: {
      'User-Agent': USER_AGENT,
      'Accept-Language': 'en-US,en;q=0.9',
    },
    signal: AbortSignal.timeout(7000),
  });

  if (!res.ok) {
    throw new Error(`Geocoding service returned HTTP ${res.status}.`);
  }

  const data = (await res.json()) as Array<{
    lat: string;
    lon: string;
    display_name: string;
  }>;

  if (data.length === 0) {
    throw new Error(`ZERO_RESULTS: Could not find '${cleaned}'.`);
  }

  return {
    lat: Number.parseFloat(data[0].lat),
    lon: Number.parseFloat(data[0].lon),
    displayName: data[0].display_name,
    method: 'OpenStreetMap Nominatim (English)',
  };
}

async function reverseGeocodeEnglish(lat: number, lon: number): Promise<string> {
  const apiKey = getGoogleApiKey();

  if (apiKey) {
    try {
      const url = new URL('https://geocode.googleapis.com/v4/geocode/location');
      url.searchParams.set('location.latitude', String(lat));
      url.searchParams.set('location.longitude', String(lon));
      url.searchParams.set('languageCode', 'en');
      url.searchParams.set('regionCode', 'IN');

      const res = await fetch(url.toString(), {
        headers: {
          'Content-Type': 'application/json',
          'X-Goog-Api-Key': apiKey,
          'X-Goog-FieldMask': 'results.placeId,results.formattedAddress',
          'X-Goog-Maps-Solution-ID': SOLUTION_ID,
        },
        signal: AbortSignal.timeout(6000),
      });

      if (res.ok) {
        const data = (await res.json()) as {
          results?: Array<{ formattedAddress?: string }>;
        };
        if (data.results?.[0]?.formattedAddress) {
          return data.results[0].formattedAddress;
        }
      }
    } catch {
      // Fallback below
    }
  }

  try {
    const url = new URL('https://nominatim.openstreetmap.org/reverse');
    url.searchParams.set('lat', String(lat));
    url.searchParams.set('lon', String(lon));
    url.searchParams.set('format', 'json');
    url.searchParams.set('accept-language', 'en');

    const res = await fetch(url.toString(), {
      headers: {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.9',
      },
      signal: AbortSignal.timeout(6000),
    });

    if (res.ok) {
      const data = (await res.json()) as { display_name?: string };
      if (data.display_name) {
        return data.display_name;
      }
    }
  } catch {
    // Coordinate fallback
  }

  return `${lat.toFixed(5)}, ${lon.toFixed(5)}`;
}

async function searchGooglePlacesNearby(
  lat: number,
  lon: number,
  radiusMeters: number,
  apiKey: string
): Promise<{ parkings: RealParkingSpot[]; error?: string }> {
  const fieldMask = [
    'places.id',
    'places.displayName',
    'places.formattedAddress',
    'places.location',
    'places.googleMapsUri',
    'places.googleMapsLinks',
  ].join(',');

  try {
    const res = await fetch('https://places.googleapis.com/v1/places:searchNearby', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': apiKey,
        'X-Goog-FieldMask': fieldMask,
        'X-Goog-Maps-Solution-ID': SOLUTION_ID,
      },
      body: JSON.stringify({
        includedTypes: ['parking'],
        maxResultCount: 20,
        rankPreference: 'DISTANCE',
        languageCode: 'en',
        regionCode: 'IN',
        locationRestriction: {
          circle: {
            center: { latitude: lat, longitude: lon },
            radius: radiusMeters,
          },
        },
      }),
      signal: AbortSignal.timeout(10000),
    });

    const data = (await res.json()) as {
      places?: Array<{
        id?: string;
        displayName?: { text?: string; languageCode?: string };
        formattedAddress?: string;
        location?: { latitude?: number; longitude?: number };
        googleMapsUri?: string;
        googleMapsLinks?: { directionsUri?: string };
      }>;
      error?: { status?: string; message?: string };
    };

    if (!res.ok) {
      const status = data.error?.status ?? `HTTP_${res.status}`;
      const message = data.error?.message ?? 'Google Places API request failed.';
      return {
        parkings: [],
        error:
          res.status === 401 || res.status === 403
            ? `REQUEST_DENIED (${status}): ${message}`
            : `Google Places API error (${status}): ${message}`,
      };
    }

    const rawPlaces = data.places ?? [];
    if (rawPlaces.length === 0) {
      return {
        parkings: [],
        error: `ZERO_RESULTS: No parking facilities found within ${Math.round(radiusMeters)} m.`,
      };
    }

    const results: RealParkingSpot[] = [];
    for (const place of rawPlaces) {
      const pLat = place.location?.latitude;
      const pLon = place.location?.longitude;
      if (typeof pLat !== 'number' || typeof pLon !== 'number') continue;

      const placeId = place.id ?? '';
      const name = place.displayName?.text?.trim() || 'Parking Facility';
      const address = place.formattedAddress?.trim() || 'Address unavailable';
      const distanceKm = haversineKm(lat, lon, pLat, pLon);
      const directionsUri =
        place.googleMapsLinks?.directionsUri ||
        `https://www.google.com/maps/dir/?api=1&origin=${lat},${lon}&destination=${pLat},${pLon}&destination_place_id=${encodeURIComponent(
          placeId
        )}`;

      results.push({
        id: placeId || `${pLat},${pLon}`,
        placeId,
        name,
        address,
        lat: pLat,
        lon: pLon,
        distanceKm,
        directionsUri,
        dataSource: 'Google Places API (New)',
        availabilityStatus: 'Availability unknown (No verified real-time occupancy feed)',
      });
    }

    if (results.length === 0) {
      return {
        parkings: [],
        error: `ZERO_RESULTS: No parking coordinates returned within ${Math.round(radiusMeters)} m.`,
      };
    }

    results.sort((a, b) => a.distanceKm - b.distanceKm);
    return { parkings: results };
  } catch (err) {
    return {
      parkings: [],
      error:
        err instanceof Error
          ? `Network error calling Google Places API: ${err.message}`
          : 'Network error calling Google Places API.',
    };
  }
}

async function searchOsmEnglishFallback(
  lat: number,
  lon: number,
  radiusMeters: number
): Promise<{ parkings: RealParkingSpot[]; error?: string }> {
  // First try Nominatim bounded search with accept-language=en (reliable and fast)
  const deltaDeg = Math.max(0.015, radiusMeters / 111000);
  const viewbox = `${lon - deltaDeg},${lat + deltaDeg},${lon + deltaDeg},${lat - deltaDeg}`;

  try {
    const url = new URL('https://nominatim.openstreetmap.org/search');
    url.searchParams.set('q', 'parking');
    url.searchParams.set('format', 'json');
    url.searchParams.set('addressdetails', '1');
    url.searchParams.set('extratags', '1');
    url.searchParams.set('accept-language', 'en');
    url.searchParams.set('limit', '20');
    url.searchParams.set('bounded', '1');
    url.searchParams.set('viewbox', viewbox);

    const res = await fetch(url.toString(), {
      headers: {
        'User-Agent': USER_AGENT,
        Accept: 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      signal: AbortSignal.timeout(8000),
    });

    if (res.ok) {
      const items = (await res.json()) as Array<{
        osm_type?: string;
        osm_id?: number;
        lat: string;
        lon: string;
        class?: string;
        type?: string;
        name?: string;
        display_name?: string;
        extratags?: Record<string, string> | null;
      }>;

      const seenCoords = new Set<string>();
      const results: RealParkingSpot[] = [];

      for (const item of items) {
        if (item.class !== 'amenity' && !(item.type ?? '').includes('parking')) continue;
        const pLat = Number.parseFloat(item.lat);
        const pLon = Number.parseFloat(item.lon);
        if (!Number.isFinite(pLat) || !Number.isFinite(pLon)) continue;

        const key = `${pLat.toFixed(5)},${pLon.toFixed(5)}`;
        if (seenCoords.has(key)) continue;
        seenCoords.add(key);

        if (item.extratags?.access === 'private') continue;

        const name = (item.name ?? '').trim() || 'Public Parking Area';
        const address = (item.display_name ?? '').trim() || `${pLat.toFixed(5)}, ${pLon.toFixed(5)}`;
        const distanceKm = haversineKm(lat, lon, pLat, pLon);

        results.push({
          id: `${item.osm_type ?? 'node'}/${item.osm_id ?? key}`,
          placeId: `${item.osm_type ?? 'node'}/${item.osm_id ?? key}`,
          name,
          address,
          lat: pLat,
          lon: pLon,
          distanceKm,
          directionsUri: `https://www.google.com/maps/dir/?api=1&origin=${lat},${lon}&destination=${pLat},${pLon}`,
          dataSource: 'OpenStreetMap (English — configure GOOGLE_MAPS_API_KEY for Google Places)',
          availabilityStatus: 'Availability unknown (No verified real-time occupancy feed)',
        });
      }

      if (results.length > 0) {
        results.sort((a, b) => a.distanceKm - b.distanceKm);
        return { parkings: results };
      }
    }
  } catch {
    // Try Overpass race if Nominatim failed
  }

  // Overpass English tag fallback
  const query = `[out:json][timeout:8];nwr["amenity"="parking"](around:${Math.min(
    radiusMeters,
    3000
  )},${lat},${lon});out center;`;

  try {
    const payload = await Promise.any(
      OVERPASS_ENDPOINTS.map(async (endpoint) => {
        const url = new URL(endpoint);
        url.searchParams.set('data', query);
        const res = await fetch(url.toString(), {
          headers: { 'User-Agent': USER_AGENT, Accept: 'application/json' },
          signal: AbortSignal.timeout(5000),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return (await res.json()) as {
          elements?: Array<{
            id: number;
            type: string;
            lat?: number;
            lon?: number;
            center?: { lat: number; lon: number };
            tags?: Record<string, string | undefined>;
          }>;
        };
      })
    );

    const results: RealParkingSpot[] = [];
    for (const el of payload.elements ?? []) {
      const tags = el.tags ?? {};
      if (tags.access === 'private') continue;
      const pLat = el.lat ?? el.center?.lat;
      const pLon = el.lon ?? el.center?.lon;
      if (typeof pLat !== 'number' || typeof pLon !== 'number') continue;

      const name = tags['name:en'] || tags.name || 'Public Parking Lot';
      const addressParts = [
        tags['addr:street:en'] || tags['addr:street'],
        tags['addr:suburb'] || tags['addr:city'],
      ].filter(Boolean);
      const address =
        addressParts.length > 0 ? addressParts.join(', ') : `${pLat.toFixed(5)}, ${pLon.toFixed(5)}`;

      results.push({
        id: `${el.type}/${el.id}`,
        placeId: `${el.type}/${el.id}`,
        name,
        address,
        lat: pLat,
        lon: pLon,
        distanceKm: haversineKm(lat, lon, pLat, pLon),
        directionsUri: `https://www.google.com/maps/dir/?api=1&origin=${lat},${lon}&destination=${pLat},${pLon}`,
        dataSource: 'OpenStreetMap (English — configure GOOGLE_MAPS_API_KEY for Google Places)',
        availabilityStatus: 'Availability unknown (No verified real-time occupancy feed)',
      });
    }

    if (results.length === 0) {
      return {
        parkings: [],
        error: `ZERO_RESULTS: No mapped parking locations found within ${Math.round(radiusMeters)} m.`,
      };
    }

    results.sort((a, b) => a.distanceKm - b.distanceKm);
    return { parkings: results };
  } catch {
    return {
      parkings: [],
      error: `ZERO_RESULTS: No parking facilities found within ${Math.round(radiusMeters)} m.`,
    };
  }
}

async function startServer() {
  const app = express();
  app.use(express.json());

  // ================= AUTH ROUTES =================
  app.post('/api/auth/login', (req, res) => {
    const { username, password } = req.body as { username?: string; password?: string };
    const u = (username ?? '').trim();
    const p = password ?? '';

    if (!u || !p) {
      res.status(400).json({ error: 'Please enter both username and password.' });
      return;
    }

    const users = loadUsers();
    const hashed = hashPassword(p);
    const user = users.find(
      (item) => item.username === u && (item.password === p || item.password === hashed)
    );

    if (!user) {
      res.status(401).json({ error: 'Invalid username or password. Please try again.' });
      return;
    }

    res.json({
      user: {
        username: user.username,
        email: user.email ?? '',
      },
    });
  });

  app.post('/api/auth/register', (req, res) => {
    const { username, password, email } = req.body as {
      username?: string;
      password?: string;
      email?: string;
    };
    const u = (username ?? '').trim();
    const p = password ?? '';
    const e = (email ?? '').trim();

    if (!u || u.length < 3) {
      res.status(400).json({ error: 'Username must be at least 3 characters long.' });
      return;
    }
    if (!p || p.length < 4) {
      res.status(400).json({ error: 'Password must be at least 4 characters long.' });
      return;
    }

    const users = loadUsers();
    if (users.some((item) => item.username === u)) {
      res.status(409).json({ error: `Username '${u}' is already taken.` });
      return;
    }

    users.push({
      username: u,
      password: hashPassword(p),
      email: e,
    });
    saveUsers(users);

    res.json({ ok: true, message: 'Account created successfully! You can now log in.' });
  });

  app.post('/api/auth/change-password', (req, res) => {
    const { username, currentPassword, newPassword, confirmPassword } = req.body as {
      username?: string;
      currentPassword?: string;
      newPassword?: string;
      confirmPassword?: string;
    };

    const u = (username ?? '').trim();
    const cur = currentPassword ?? '';
    const next = newPassword ?? '';
    const cfm = confirmPassword ?? '';

    if (!u || !cur || !next || !cfm) {
      res.status(400).json({ error: 'All password fields are required.' });
      return;
    }
    if (next !== cfm) {
      res.status(400).json({ error: 'New password and confirmation do not match.' });
      return;
    }
    if (next.length < 4) {
      res.status(400).json({ error: 'New password must be at least 4 characters long.' });
      return;
    }

    const users = loadUsers();
    const curHash = hashPassword(cur);
    const target = users.find((item) => item.username === u);

    if (!target) {
      res.status(404).json({ error: 'User account not found.' });
      return;
    }
    if (target.password !== cur && target.password !== curHash) {
      res.status(401).json({ error: 'Current password is incorrect.' });
      return;
    }

    target.password = hashPassword(next);
    saveUsers(users);
    res.json({ ok: true, message: 'Password updated successfully!' });
  });

  // ================= REAL ENGLISH LOCATION & PARKING ROUTES =================
  app.get('/api/location/reverse', async (req, res) => {
    const lat = Number.parseFloat(String(req.query.lat ?? ''));
    const lon = Number.parseFloat(String(req.query.lon ?? ''));
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      res.status(400).json({ error: 'Valid latitude and longitude are required.' });
      return;
    }
    const displayName = await reverseGeocodeEnglish(lat, lon);
    res.json({ lat, lon, displayName, method: 'Device Geolocation (GPS)' });
  });

  app.get('/api/parking', async (req, res) => {
    const locationQuery = String(req.query.location ?? '').trim();
    const latParam = Number.parseFloat(String(req.query.lat ?? ''));
    const lonParam = Number.parseFloat(String(req.query.lon ?? ''));
    const radiusParam = Number.parseFloat(String(req.query.radius ?? '3000'));
    const radiusMeters = Number.isFinite(radiusParam)
      ? Math.max(100, Math.min(50000, radiusParam))
      : 3000;

    let lat = latParam;
    let lon = lonParam;
    let displayName = locationQuery;
    let method = 'Device Geolocation (GPS)';

    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      if (!locationQuery) {
        res.status(400).json({ error: 'Please enter a city or address (e.g., Faridabad, Haryana, India).' });
        return;
      }

      try {
        const geocoded = await geocodeEnglish(locationQuery);
        lat = geocoded.lat;
        lon = geocoded.lon;
        displayName = geocoded.displayName;
        method = geocoded.method;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Geocoding failed.';
        res.status(msg.startsWith('ZERO_RESULTS') ? 404 : 502).json({ error: msg });
        return;
      }
    } else if (!displayName) {
      displayName = await reverseGeocodeEnglish(lat, lon);
    }

    const apiKey = getGoogleApiKey();
    const searchResult = apiKey
      ? await searchGooglePlacesNearby(lat, lon, radiusMeters, apiKey)
      : await searchOsmEnglishFallback(lat, lon, radiusMeters);

    if (searchResult.error) {
      res.status(searchResult.error.startsWith('ZERO_RESULTS') ? 404 : 502).json({
        error: searchResult.error,
        location: { lat, lon, displayName, method },
      });
      return;
    }

    res.json({
      location: { lat, lon, displayName, method },
      parkings: searchResult.parkings,
    });
  });

  // ================= VITE / STATIC MIDDLEWARE =================
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distDir = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distDir));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distDir, 'index.html'));
    });
  }

  app.listen(3000, '0.0.0.0', () => {
    console.log('Smart Parking Finder server running on http://0.0.0.0:3000');
  });
}

startServer();
