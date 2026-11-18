"""
location_service.py
Real-time device location detection using OS/GPS location services
(Windows Location Services via WinRT Geolocator, macOS CoreLocation, Linux gpsd/GeoClue2)
and English-forced reverse geocoding via Google Geocoding API v4.
Never uses IP-based geolocation or hardcoded coordinates as a substitute for GPS/device location.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

import requests

USER_AGENT = "SmartParkingFinderDesktop/2.0"
SOLUTION_ID = "gmp_mcp_codeassist_v1_aistudio"


def load_env_key() -> str:
    """Read GOOGLE_MAPS_API_KEY from environment or local .env file."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    k, v = stripped.split("=", 1)
                    if k.strip() == "GOOGLE_MAPS_API_KEY":
                        return v.strip().strip('"').strip("'")
        except OSError:
            pass
    return ""


@dataclass
class LocationResult:
    latitude: float
    longitude: float
    display_name: str
    area: str
    detection_method: str
    accuracy_note: str


def reverse_geocode_english(lat: float, lon: float) -> str:
    """Reverse geocode coordinates strictly in English using Google Geocoding API v4."""
    api_key = load_env_key()
    if api_key:
        try:
            resp = requests.get(
                "https://geocode.googleapis.com/v4/geocode/location",
                params={
                    "location.latitude": lat,
                    "location.longitude": lon,
                    "languageCode": "en",
                    "regionCode": "IN",
                },
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": "results.placeId,results.formattedAddress",
                    "X-Goog-Maps-Solution-ID": SOLUTION_ID,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results and results[0].get("formattedAddress"):
                    return str(results[0]["formattedAddress"])
        except requests.RequestException:
            pass

    return f"{lat:.5f}, {lon:.5f}"


def _detect_windows_location() -> tuple[Optional[tuple[float, float, str]], Optional[str]]:
    """
    Query Windows Location Services using Windows.Devices.Geolocation.Geolocator.
    Uses WinRT Python bindings if installed, otherwise Windows PowerShell WinRT.
    """
    # 1. Try Python WinRT bindings (winsdk or winrt) if available
    try:
        import asyncio
        try:
            from winrt.windows.devices.geolocation import (  # type: ignore
                GeolocationAccessStatus,
                Geolocator,
                PositionAccuracy,
            )
        except ImportError:
            from winsdk.windows.devices.geolocation import (  # type: ignore
                GeolocationAccessStatus,
                Geolocator,
                PositionAccuracy,
            )

        async def _query() -> tuple[Optional[tuple[float, float, str]], Optional[str]]:
            access = await Geolocator.request_access_async()
            if access == GeolocationAccessStatus.DENIED:
                return None, (
                    "Location permission was denied in Windows Settings. "
                    "Enable 'Location access' for desktop apps in Settings > Privacy & security > Location, then click Retry."
                )
            if access != GeolocationAccessStatus.ALLOWED:
                return None, (
                    "Windows Location Services are currently unavailable. "
                    "Turn on Location Services in Windows Settings and click Retry."
                )

            geolocator = Geolocator()
            geolocator.desired_accuracy = PositionAccuracy.HIGH
            pos = await geolocator.get_geoposition_async()
            coord = pos.coordinate.point.position
            acc = getattr(pos.coordinate, "accuracy", None)
            note = f"Windows Location Services (accuracy ~{int(acc)} m)" if acc else "Windows Location Services"
            return (float(coord.latitude), float(coord.longitude), note), None

        return asyncio.run(_query())
    except ImportError:
        pass
    except Exception as exc:
        return None, f"Unable to read Windows Location Services ({exc}). Please ensure GPS/Location is enabled and click Retry."

    # 2. Built-in Windows PowerShell WinRT bridge (no extra compiled packages required)
    ps_script = r"""
$ErrorActionPreference = 'Stop'
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]
    function Await($WinRtTask, $ResultType) {
        $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
        $netTask = $asTask.Invoke($null, @($WinRtTask))
        $netTask.Wait(10000) | Out-Null
        if (-not $netTask.IsCompleted) { throw 'TIMEOUT' }
        return $netTask.Result
    }
    [Windows.Devices.Geolocation.Geolocator,Windows.Devices.Geolocation,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Geolocation.GeolocationAccessStatus,Windows.Devices.Geolocation,ContentType=WindowsRuntime] | Out-Null
    [Windows.Devices.Geolocation.Geoposition,Windows.Devices.Geolocation,ContentType=WindowsRuntime] | Out-Null

    $access = Await ([Windows.Devices.Geolocation.Geolocator]::RequestAccessAsync()) ([Windows.Devices.Geolocation.GeolocationAccessStatus])
    if ($access -eq 'Denied') {
        Write-Output 'ERR:DENIED'
        exit 0
    }
    if ($access -ne 'Allowed') {
        Write-Output "ERR:UNAVAILABLE:$access"
        exit 0
    }
    $geo = New-Object Windows.Devices.Geolocation.Geolocator
    $geo.DesiredAccuracy = 'High'
    $pos = Await ($geo.GetGeopositionAsync()) ([Windows.Devices.Geolocation.Geoposition])
    $p = $pos.Coordinate.Point.Position
    $acc = $pos.Coordinate.Accuracy
    Write-Output ("OK:{0},{1},{2}" -f $p.Latitude, $p.Longitude, $acc)
} catch {
    Write-Output ("ERR:EXCEPTION:" + $_.Exception.Message)
}
"""
    ps_exe = shutil.which("powershell.exe") or shutil.which("powershell")
    if not ps_exe:
        return None, (
            "Windows Location Services require PowerShell or Python winsdk. "
            "Verify Windows Location Services are enabled and click Retry."
        )

    try:
        proc = subprocess.run(
            [ps_exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=14,
            check=False,
        )
        output = (proc.stdout or "").strip().splitlines()
        last_line = output[-1].strip() if output else ""
        if last_line.startswith("OK:"):
            parts = last_line[3:].split(",")
            lat = float(parts[0])
            lon = float(parts[1])
            acc_str = parts[2] if len(parts) > 2 else ""
            note = (
                f"Windows Location Services (accuracy ~{int(float(acc_str))} m)"
                if acc_str
                else "Windows Location Services"
            )
            return (lat, lon, note), None
        if last_line == "ERR:DENIED":
            return None, (
                "Location permission was denied. Enable Windows Location access in "
                "Settings > Privacy & security > Location, then click Retry."
            )
        if last_line.startswith("ERR:UNAVAILABLE"):
            return None, (
                "Windows Location Services are turned off or unavailable. "
                "Enable Location Services on your device and click Retry."
            )
        if "TIMEOUT" in last_line:
            return None, "Timed out waiting for device GPS/Windows Location Services. Please click Retry."
        detail = last_line.replace("ERR:EXCEPTION:", "") or (proc.stderr or "").strip() or "GPS unavailable"
        return None, f"Unable to obtain device location ({detail}). Please check location settings and click Retry."
    except subprocess.TimeoutExpired:
        return None, "Timed out waiting for Windows Location Services. Please click Retry."
    except Exception as exc:
        return None, f"Failed to access Windows Location Services ({exc}). Please click Retry."


def _detect_linux_gps_location() -> tuple[Optional[tuple[float, float, str]], Optional[str]]:
    """Query hardware GPS via gpsd (gpspipe) if available on Linux."""
    gpspipe_exe = shutil.which("gpspipe")
    if gpspipe_exe:
        try:
            proc = subprocess.run(
                [gpspipe_exe, "-w", "-n", "6"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in (proc.stdout or "").splitlines():
                try:
                    pkt = json.loads(line)
                except ValueError:
                    continue
                if pkt.get("class") == "TPV" and "lat" in pkt and "lon" in pkt:
                    return (float(pkt["lat"]), float(pkt["lon"]), "Device GPS (gpsd)"), None
        except Exception:
            pass

    return None, (
        "Device GPS / OS location service is unavailable in this environment. "
        "Please enable device GPS/location services (or run in a browser/Windows desktop with location enabled) and click Retry."
    )


def _detect_macos_location() -> tuple[Optional[tuple[float, float, str]], Optional[str]]:
    """Query macOS CoreLocation if pyobjc CoreLocation is installed."""
    try:
        import time
        import CoreLocation  # type: ignore

        manager = CoreLocation.CLLocationManager.alloc().init()
        status = CoreLocation.CLLocationManager.authorizationStatus()
        # 2 = Denied, 1 = Restricted
        if status in (1, 2):
            return None, (
                "Location permission was denied in macOS Privacy Settings. "
                "Allow Location Services and click Retry."
            )
        manager.startUpdatingLocation()
        for _ in range(16):
            loc = manager.location()
            if loc is not None:
                coord = loc.coordinate()
                manager.stopUpdatingLocation()
                return (float(coord.latitude), float(coord.longitude), "macOS CoreLocation"), None
            time.sleep(0.3)
        manager.stopUpdatingLocation()
        return None, "Timed out waiting for macOS Location Services. Please click Retry."
    except ImportError:
        return None, (
            "macOS Location Services require PyObjC CoreLocation, or run on Windows/browser with GPS enabled. "
            "Please click Retry once available."
        )
    except Exception as exc:
        return None, f"Unable to access macOS Location Services ({exc}). Please click Retry."


def detect_device_location() -> tuple[Optional[LocationResult], Optional[str]]:
    """
    Obtain the device's real-time latitude and longitude using OS/GPS location services.
    Never substitutes IP-based geolocation or hardcoded coordinates.
    """
    coords: Optional[tuple[float, float, str]] = None
    err: Optional[str] = None

    if sys.platform == "win32":
        coords, err = _detect_windows_location()
    elif sys.platform == "darwin":
        coords, err = _detect_macos_location()
    else:
        coords, err = _detect_linux_gps_location()

    if err or coords is None:
        return None, err or "Device GPS or location services are unavailable. Please click Retry."

    lat, lon, method = coords
    english_address = reverse_geocode_english(lat, lon)
    return (
        LocationResult(
            latitude=lat,
            longitude=lon,
            display_name=english_address,
            area=english_address,
            detection_method=method,
            accuracy_note="Real-time coordinates from device location services.",
        ),
        None,
    )


# Backward-compatible alias if imported elsewhere
detect_approximate_location = detect_device_location

