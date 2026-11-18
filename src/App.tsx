import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

interface UserSession {
  username: string;
  email: string;
}

interface LocationInfo {
  lat: number;
  lon: number;
  displayName: string;
  method: string;
}

interface ParkingSpot {
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

function createPinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'custom-pin',
    html: `<div style="width:18px;height:18px;border-radius:50%;background:${color};border:3px solid #ffffff;box-shadow:0 2px 5px rgba(0,0,0,0.45);"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
    popupAnchor: [0, -10],
  });
}

function ParkingMap({
  location,
  parkings,
  selected,
  onSelect,
}: {
  location: LocationInfo | null;
  parkings: ParkingSpot[];
  selected: ParkingSpot | null;
  onSelect: (spot: ParkingSpot) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current).setView([20, 0], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    const layer = L.layerGroup().addTo(map);
    mapRef.current = map;
    layerRef.current = layer;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (!location) return;

    map.setView([location.lat, location.lon], 14);

    L.marker([location.lat, location.lon], {
      icon: createPinIcon('#2563eb'),
    })
      .bindPopup(
        `<strong>Your Location</strong><br/>${location.displayName}<br/>${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}`
      )
      .addTo(layer);

    for (const p of parkings) {
      const isSelected = selected?.id === p.id;
      const marker = L.marker([p.lat, p.lon], {
        icon: createPinIcon(isSelected ? '#059669' : '#10b981'),
      })
        .bindPopup(
          `<strong>${p.name}</strong><br/>${p.address}<br/>Distance: ${p.distanceKm.toFixed(2)} km`
        )
        .addTo(layer);
      marker.on('click', () => onSelect(p));
    }
  }, [location, parkings, selected, onSelect]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}

export default function App() {
  // Login & Registration State
  const [session, setSession] = useState<UserSession | null>(null);
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');
  const [authBusy, setAuthBusy] = useState(false);

  // Main Screen State (ONLY 2 options: Find Parking & Change Password)
  const [activeOption, setActiveOption] = useState<'find' | 'password'>('find');
  const [currentLocation, setCurrentLocation] = useState<LocationInfo | null>(null);
  const [radiusMeters, setRadiusMeters] = useState('3000');
  const [parkings, setParkings] = useState<ParkingSpot[]>([]);
  const [selectedParking, setSelectedParking] = useState<ParkingSpot | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState(
    "Click 'Find Parking' to automatically detect your current device location."
  );
  const [errorMsg, setErrorMsg] = useState('');

  // Change Password State
  const [curPwd, setCurPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [cfmPwd, setCfmPwd] = useState('');
  const [pwdError, setPwdError] = useState('');
  const [pwdSuccess, setPwdSuccess] = useState('');
  const [pwdBusy, setPwdBusy] = useState(false);

  async function handleAuthSubmit(e: React.FormEvent) {
    e.preventDefault();
    setAuthError('');
    setAuthSuccess('');
    setAuthBusy(true);

    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body =
        authMode === 'login'
          ? { username, password }
          : { username, password, email };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (!res.ok) {
        setAuthError(data.error || 'Authentication failed.');
        return;
      }

      if (authMode === 'login') {
        setSession(data.user);
        setActiveOption('find');
        setCurrentLocation(null);
        setParkings([]);
        setSelectedParking(null);
        setErrorMsg('');
        setStatusMessage(
          "Click 'Find Parking' to automatically detect your current device location."
        );
      } else {
        setAuthMode('login');
        setPassword('');
        setAuthSuccess(data.message || 'Account created! You can now log in.');
      }
    } catch {
      setAuthError('Unable to reach server. Please check your connection.');
    } finally {
      setAuthBusy(false);
    }
  }

  async function queryParkingApi(params: URLSearchParams) {
    const res = await fetch(`/api/parking?${params.toString()}`);
    const data = await res.json();

    if (!res.ok) {
      if (data.location) {
        setCurrentLocation(data.location);
      }
      setParkings([]);
      setSelectedParking(null);
      throw new Error(data.error || 'Failed to fetch parking locations.');
    }

    setCurrentLocation(data.location);
    setParkings(data.parkings ?? []);
    setSelectedParking(data.parkings?.[0] ?? null);
    setStatusMessage(
      `Found ${data.parkings?.length ?? 0} English parking result(s) within ${radiusMeters} m.`
    );
  }

  async function handleFindParkingLive() {
    if (isLoading) return;
    setIsLoading(true);
    setErrorMsg('');
    setStatusMessage('Fetching your current device location...');

    if (!navigator.geolocation) {
      setIsLoading(false);
      setErrorMsg(
        'Device location services are not supported in this browser. Please enable location support and click Retry.'
      );
      setStatusMessage('Device location unavailable.');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          setStatusMessage('Device coordinates acquired. Searching nearby parking...');
          const params = new URLSearchParams({
            lat: String(lat),
            lon: String(lon),
            radius: radiusMeters || '3000',
          });
          await queryParkingApi(params);
        } catch (err) {
          setErrorMsg(err instanceof Error ? err.message : 'Unable to fetch nearby parking.');
          setStatusMessage('Parking search returned an error.');
        } finally {
          setIsLoading(false);
        }
      },
      (geoErr) => {
        setIsLoading(false);
        setStatusMessage('Location permission denied or GPS unavailable.');
        if (geoErr.code === geoErr.PERMISSION_DENIED) {
          setErrorMsg(
            'Location permission was denied. Please allow location access in your browser/device settings and click Retry.'
          );
        } else if (geoErr.code === geoErr.POSITION_UNAVAILABLE) {
          setErrorMsg(
            'Device GPS or location services are currently unavailable. Ensure location services are enabled and click Retry.'
          );
        } else {
          setErrorMsg(
            `Timed out while fetching device location (${geoErr.message}). Please click Retry.`
          );
        }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setPwdError('');
    setPwdSuccess('');
    setPwdBusy(true);

    try {
      const res = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: session.username,
          currentPassword: curPwd,
          newPassword: newPwd,
          confirmPassword: cfmPwd,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setPwdError(data.error || 'Failed to update password.');
        return;
      }

      setPwdSuccess(data.message || 'Password updated successfully!');
      setCurPwd('');
      setNewPwd('');
      setCfmPwd('');
    } catch {
      setPwdError('Unable to reach server.');
    } finally {
      setPwdBusy(false);
    }
  }

  function handleLogout() {
    setSession(null);
    setPassword('');
    setAuthError('');
    setAuthSuccess('');
    setCurrentLocation(null);
    setParkings([]);
    setSelectedParking(null);
  }

  // ================= LOGIN SCREEN =================
  if (!session) {
    return (
      <div className="auth-wrapper">
        <div className="auth-card">
          <div className="brand-pill">SMART PARKING FINDER</div>
          <h1 className="auth-title">{authMode === 'login' ? 'Login' : 'Create Account'}</h1>
          <p className="auth-subtitle">
            {authMode === 'login'
              ? 'Sign in with your username and password'
              : 'Register a new Smart Parking Finder account'}
          </p>

          {authError && (
            <div className="banner-error" style={{ marginBottom: 12, textAlign: 'left' }}>
              {authError}
            </div>
          )}
          {authSuccess && (
            <div className="banner-success" style={{ marginBottom: 12, textAlign: 'left' }}>
              {authSuccess}
            </div>
          )}

          <form onSubmit={handleAuthSubmit}>
            <div className="field">
              <label htmlFor="auth-username">Username</label>
              <input
                id="auth-username"
                className="input"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            {authMode === 'register' && (
              <div className="field">
                <label htmlFor="auth-email">Email (optional)</label>
                <input
                  id="auth-email"
                  className="input"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}

            <div className="field">
              <label htmlFor="auth-password">Password</label>
              <div className="pwd-row">
                <input
                  id="auth-password"
                  className="input"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="btn btn-light"
                  onClick={() => setShowPassword((prev) => !prev)}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-green btn-full"
              disabled={authBusy}
              style={{ marginTop: 6 }}
            >
              {authBusy ? 'Please wait...' : authMode === 'login' ? 'Login' : 'Create Account'}
            </button>
          </form>

          <button
            type="button"
            className="btn btn-link"
            style={{ marginTop: 12 }}
            onClick={() => {
              setAuthError('');
              setAuthSuccess('');
              setAuthMode(authMode === 'login' ? 'register' : 'login');
            }}
          >
            {authMode === 'login'
              ? "Don't have an account? Register"
              : 'Already have an account? Login'}
          </button>
        </div>
      </div>
    );
  }

  // ================= MAIN SCREEN =================
  return (
    <div className="main-shell">
      <header className="topbar">
        <h1 className="topbar-title">Smart Parking Finder</h1>

        <div className="topbar-actions">
          <span className="user-label">User: {session.username}</span>

          <button
            type="button"
            className={`btn ${activeOption === 'find' ? 'btn-green' : 'btn-navy'}`}
            onClick={() => setActiveOption('find')}
          >
            Find Parking
          </button>

          <button
            type="button"
            className={`btn ${activeOption === 'password' ? 'btn-green' : 'btn-navy'}`}
            onClick={() => {
              setPwdError('');
              setPwdSuccess('');
              setActiveOption('password');
            }}
          >
            Change Password
          </button>

          <button type="button" className="btn btn-danger" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="content-area">
        {activeOption === 'find' ? (
          <>
            <div className="card find-header-card">
              <button
                type="button"
                className="btn btn-green btn-lg"
                disabled={isLoading}
                onClick={() => void handleFindParkingLive()}
              >
                {isLoading ? (
                  <>
                    <span className="spinner spinner-light" aria-hidden="true" />
                    <span>Locating...</span>
                  </>
                ) : (
                  'Find Parking'
                )}
              </button>

              <div className="find-location-info">
                <p className="find-location-title">
                  {currentLocation
                    ? `Location: ${currentLocation.displayName} (${currentLocation.lat.toFixed(5)}, ${currentLocation.lon.toFixed(5)})`
                    : 'Current Location: Not detected yet'}
                </p>
                <p className="find-location-sub" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {isLoading && <span className="spinner" aria-hidden="true" />}
                  <span>
                    {currentLocation ? `${currentLocation.method} — ${statusMessage}` : statusMessage}
                  </span>
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label htmlFor="radius-input" style={{ fontWeight: 700, fontSize: 13 }}>
                  Radius (m):
                </label>
                <input
                  id="radius-input"
                  className="input"
                  type="number"
                  min={100}
                  max={50000}
                  style={{ width: 92 }}
                  value={radiusMeters}
                  onChange={(e) => setRadiusMeters(e.target.value)}
                />
              </div>
            </div>

            {errorMsg && (
              <div className="banner-error">
                <span>{errorMsg}</span>
                <button
                  type="button"
                  className="btn btn-navy"
                  disabled={isLoading}
                  onClick={() => void handleFindParkingLive()}
                >
                  Retry
                </button>
              </div>
            )}

            <div className="workspace-grid">
              <div className="card">
                <div className="map-container">
                  <ParkingMap
                    location={currentLocation}
                    parkings={parkings}
                    selected={selectedParking}
                    onSelect={setSelectedParking}
                  />
                </div>

                <div style={{ marginBottom: 8, fontWeight: 700 }}>
                  Parking Locations ({parkings.length})
                </div>

                {parkings.length === 0 ? (
                  <p style={{ color: '#64748b', margin: 0, fontSize: 14 }}>
                    Click &apos;Find Parking&apos; to automatically detect your current device location and display genuine nearby parking facilities.
                  </p>
                ) : (
                  <div className="table-wrap">
                    <table className="parking-table">
                      <thead>
                        <tr>
                          <th>Parking Name</th>
                          <th>English Address</th>
                          <th>Distance</th>
                        </tr>
                      </thead>
                      <tbody>
                        {parkings.map((p) => (
                          <tr
                            key={p.id}
                            className={selectedParking?.id === p.id ? 'selected' : ''}
                            onClick={() => setSelectedParking(p)}
                          >
                            <td>
                              <strong>{p.name}</strong>
                            </td>
                            <td>{p.address}</td>
                            <td>{p.distanceKm.toFixed(2)} km</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="card">
                <strong style={{ display: 'block', fontSize: 16, marginBottom: 12 }}>
                  Selected Parking
                </strong>

                {!selectedParking ? (
                  <p style={{ color: '#64748b', margin: 0, fontSize: 14 }}>
                    Select a parking location from the list or map to view its English details and open Google Maps directions.
                  </p>
                ) : (
                  <>
                    <div className="detail-row">
                      <div className="detail-label">Parking Name</div>
                      <div className="detail-val">
                        <strong>{selectedParking.name}</strong>
                      </div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Formatted Address</div>
                      <div className="detail-val">{selectedParking.address}</div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Distance</div>
                      <div className="detail-val">{selectedParking.distanceKm.toFixed(2)} km</div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Exact Coordinates</div>
                      <div className="detail-val">
                        {selectedParking.lat.toFixed(5)}, {selectedParking.lon.toFixed(5)}
                      </div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Place ID</div>
                      <div className="detail-val">{selectedParking.placeId || 'N/A'}</div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Data Source</div>
                      <div className="detail-val">{selectedParking.dataSource}</div>
                    </div>

                    <div className="detail-row">
                      <div className="detail-label">Availability Status</div>
                      <div className="detail-val">{selectedParking.availabilityStatus}</div>
                    </div>

                    <a
                      href={selectedParking.directionsUri}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-green btn-full"
                      style={{ textDecoration: 'none', marginTop: 10 }}
                    >
                      Open Directions in Google Maps
                    </a>
                  </>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="card password-card">
            <h2 style={{ margin: '0 0 4px' }}>Change Password</h2>
            <p style={{ margin: '0 0 16px', color: '#64748b', fontSize: 13 }}>
              Update your account password stored in users.json
            </p>

            {pwdError && (
              <div className="banner-error" style={{ marginBottom: 12 }}>
                {pwdError}
              </div>
            )}
            {pwdSuccess && (
              <div className="banner-success" style={{ marginBottom: 12 }}>
                {pwdSuccess}
              </div>
            )}

            <form onSubmit={handleChangePassword}>
              <div className="field">
                <label htmlFor="cur-pwd">Current Password</label>
                <input
                  id="cur-pwd"
                  className="input"
                  type="password"
                  value={curPwd}
                  onChange={(e) => setCurPwd(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="new-pwd">New Password</label>
                <input
                  id="new-pwd"
                  className="input"
                  type="password"
                  value={newPwd}
                  onChange={(e) => setNewPwd(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label htmlFor="cfm-pwd">Confirm New Password</label>
                <input
                  id="cfm-pwd"
                  className="input"
                  type="password"
                  value={cfmPwd}
                  onChange={(e) => setCfmPwd(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="btn btn-green btn-full" disabled={pwdBusy}>
                {pwdBusy ? 'Updating...' : 'Update Password'}
              </button>
            </form>
          </div>
        )}
      </main>
    </div>
  );
}
