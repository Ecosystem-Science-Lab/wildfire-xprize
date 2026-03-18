# Code Patterns for Satellite Fire Detection System

## 1. TLE-Based Overpass Prediction System

### Full NSW Overpass Scheduler

```python
"""
Compute all fire-relevant satellite overpasses over NSW for a given time window.
Requires: pyorbital, skyfield, sgp4
Install: pip install pyorbital skyfield sgp4 requests
"""

import json
from datetime import datetime, timedelta
from pyorbital.orbital import Orbital
import requests

# NSW bounding box
NSW_BBOX = {
    'north': -28.0,
    'south': -37.0,
    'west': 148.0,
    'east': 154.0,
    'center_lat': -32.5,
    'center_lon': 151.0
}

# Fire-relevant satellites with NORAD IDs
FIRE_SATELLITES = {
    'SUOMI NPP': {'norad': 37849, 'sensor': 'VIIRS', 'resolution': '375m', 'priority': 1},
    'NOAA 20': {'norad': 43013, 'sensor': 'VIIRS', 'resolution': '375m', 'priority': 1},
    'NOAA 21': {'norad': 54234, 'sensor': 'VIIRS', 'resolution': '375m', 'priority': 1},
    'TERRA': {'norad': 25994, 'sensor': 'MODIS', 'resolution': '1km', 'priority': 2},
    'AQUA': {'norad': 27424, 'sensor': 'MODIS', 'resolution': '1km', 'priority': 2},
    'SENTINEL-3A': {'norad': 41335, 'sensor': 'SLSTR', 'resolution': '1km', 'priority': 2},
    'SENTINEL-3B': {'norad': 43437, 'sensor': 'SLSTR', 'resolution': '1km', 'priority': 2},
    'METOP-B': {'norad': 38771, 'sensor': 'AVHRR', 'resolution': '1.1km', 'priority': 3},
    'METOP-C': {'norad': 43689, 'sensor': 'AVHRR', 'resolution': '1.1km', 'priority': 3},
    'LANDSAT 8': {'norad': 39084, 'sensor': 'TIRS+OLI', 'resolution': '100m', 'priority': 1},
    'LANDSAT 9': {'norad': 49260, 'sensor': 'TIRS+OLI', 'resolution': '100m', 'priority': 1},
}

def compute_overpasses(start_time, duration_hours=336, min_elevation=5):
    """
    Compute all satellite overpasses over NSW center point.

    Args:
        start_time: datetime, start of search window
        duration_hours: int, hours to search (default 14 days = 336 hours)
        min_elevation: float, minimum elevation angle in degrees

    Returns:
        List of overpass dicts sorted by time
    """
    all_passes = []

    for sat_name, info in FIRE_SATELLITES.items():
        try:
            orb = Orbital(sat_name)
            passes = orb.get_next_passes(
                start_time,
                duration_hours,
                NSW_BBOX['center_lon'],
                NSW_BBOX['center_lat'],
                0,  # altitude meters
                horizon=min_elevation
            )
            for rise, rise_az, max_time, max_alt, set_time, set_az in passes:
                all_passes.append({
                    'satellite': sat_name,
                    'sensor': info['sensor'],
                    'resolution': info['resolution'],
                    'priority': info['priority'],
                    'rise_utc': rise.isoformat(),
                    'max_alt_utc': max_time.isoformat(),
                    'max_elevation_deg': round(max_alt, 1),
                    'set_utc': set_time.isoformat(),
                    'duration_sec': (set_time - rise).total_seconds()
                })
        except Exception as e:
            print(f"Warning: Could not compute passes for {sat_name}: {e}")

    # Sort by maximum altitude time
    all_passes.sort(key=lambda x: x['max_alt_utc'])
    return all_passes

def save_schedule(passes, filename='nsw_overpass_schedule.json'):
    with open(filename, 'w') as f:
        json.dump(passes, f, indent=2, default=str)
    print(f"Saved {len(passes)} overpasses to {filename}")

if __name__ == '__main__':
    # Competition window: April 10-24, 2026
    start = datetime(2026, 4, 10, 0, 0, 0)
    passes = compute_overpasses(start, duration_hours=14*24)
    save_schedule(passes)

    # Print summary
    by_sensor = {}
    for p in passes:
        sensor = p['sensor']
        by_sensor[sensor] = by_sensor.get(sensor, 0) + 1

    print("\nOverpass summary for 14-day window:")
    for sensor, count in sorted(by_sensor.items()):
        print(f"  {sensor}: {count} passes ({count/14:.1f}/day)")
```

## 2. FIRMS API Client

### Query Active Fire Detections

```python
"""
Query NASA FIRMS for active fire detections over NSW.
Requires: requests
"""

import requests
import csv
import io
from datetime import datetime

class FIRMSClient:
    BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"

    def __init__(self, map_key):
        self.map_key = map_key

    def get_active_fires(self, source='VIIRS_SNPP_NRT',
                         bbox='-37,-28,148,154',
                         days=1, output='csv'):
        """
        Query active fire detections for NSW.

        Sources:
            VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT,
            MODIS_NRT, LANDSAT_NRT (US/Canada only)

        For geostationary:
            GOES_NRT, H09_NRT (Himawari-9), MSG_NRT (Meteosat)
        """
        url = f"{self.BASE_URL}/area/{output}/{self.map_key}/{source}/{bbox}/{days}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        if output == 'csv':
            reader = csv.DictReader(io.StringIO(response.text))
            return list(reader)
        return response.text

    def get_data_availability(self):
        """Check which data sources are currently available."""
        url = f"{self.BASE_URL}/data_availability/csv/{self.map_key}/ALL"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text

    def poll_fires(self, sources=None, interval_seconds=300):
        """
        Continuously poll for new fire detections.

        Args:
            sources: list of FIRMS sources to query
            interval_seconds: polling interval (default 5 min)
        """
        import time

        if sources is None:
            sources = [
                'VIIRS_SNPP_NRT',
                'VIIRS_NOAA20_NRT',
                'VIIRS_NOAA21_NRT',
                'MODIS_NRT',
                'H09_NRT',  # Himawari-9
            ]

        seen_fires = set()

        while True:
            for source in sources:
                try:
                    fires = self.get_active_fires(source=source, days=1)
                    for fire in fires:
                        # Create unique ID from lat/lon/datetime
                        fire_id = f"{fire.get('latitude','')},{fire.get('longitude','')},{fire.get('acq_date','')},{fire.get('acq_time','')}"
                        if fire_id not in seen_fires:
                            seen_fires.add(fire_id)
                            yield {
                                'source': source,
                                'latitude': float(fire.get('latitude', 0)),
                                'longitude': float(fire.get('longitude', 0)),
                                'brightness': fire.get('bright_ti4', fire.get('brightness', '')),
                                'confidence': fire.get('confidence', ''),
                                'acq_date': fire.get('acq_date', ''),
                                'acq_time': fire.get('acq_time', ''),
                                'frp': fire.get('frp', ''),
                                'satellite': fire.get('satellite', ''),
                            }
                except Exception as e:
                    print(f"Error querying {source}: {e}")

            time.sleep(interval_seconds)


# Usage
if __name__ == '__main__':
    MAP_KEY = 'YOUR_MAP_KEY_HERE'
    client = FIRMSClient(MAP_KEY)

    # One-shot query
    fires = client.get_active_fires(source='VIIRS_SNPP_NRT', days=1)
    print(f"Found {len(fires)} VIIRS fire detections in NSW")
    for fire in fires[:5]:
        print(f"  {fire}")

    # Continuous polling
    # for fire in client.poll_fires():
    #     print(f"NEW FIRE: {fire}")
```

## 3. AWS NODD Himawari Push-Driven Ingestion

### SNS-Triggered Lambda Pattern

```python
"""
AWS Lambda handler for Himawari data ingestion via SNS notification.
Triggered when new Himawari data appears in NODD S3 bucket.

Deploy as Lambda function, subscribe to Himawari SNS topic.
"""

import json
import boto3
import numpy as np

s3 = boto3.client('s3')

# Himawari NODD bucket
HIMAWARI_BUCKET = 'noaa-himawari'

def lambda_handler(event, context):
    """Process new Himawari data notification."""

    for record in event['Records']:
        # Parse SNS message
        sns_message = json.loads(record['Sns']['Message'])

        # Extract S3 object info
        for s3_record in sns_message.get('Records', []):
            bucket = s3_record['s3']['bucket']['name']
            key = s3_record['s3']['object']['key']

            # Filter for fire-relevant bands
            # Band 7 (3.9 um MIR) and Band 14 (11.2 um TIR)
            if 'B07' in key or 'B14' in key:
                process_fire_band(bucket, key)

    return {'statusCode': 200}

def process_fire_band(bucket, key):
    """
    Download and process a Himawari fire-relevant band.

    In production, this would:
    1. Download the segment/band data
    2. Convert to brightness temperature
    3. Run fire detection algorithm
    4. If fire detected, push alert
    """
    print(f"Processing fire band: s3://{bucket}/{key}")

    # Download the object
    response = s3.get_object(Bucket=bucket, Key=key)
    data = response['Body'].read()

    # Process data (placeholder -- actual implementation depends on data format)
    # Himawari Standard Data (HSD) format requires specific decoder
    # See: https://www.data.jma.go.jp/mscweb/en/himawari89/space_segment/spsg_sample.html

    # TODO: Implement fire detection
    # 1. Decode HSD format
    # 2. Extract NSW region (subset by lat/lon)
    # 3. Convert to brightness temperature
    # 4. Run contextual fire detection (MIR - TIR threshold + context)
    # 5. Filter false positives (sun glint, hot desert, clouds)
    # 6. Push alert if fire detected

    pass
```

### S3 Polling Pattern (Simpler Alternative)

```python
"""
Poll AWS NODD for new Himawari data.
Simpler than SNS but has polling latency.
"""

import boto3
import time
from datetime import datetime, timedelta

s3 = boto3.client('s3', region_name='us-east-1')

HIMAWARI_BUCKET = 'noaa-himawari'

def poll_himawari(check_interval_seconds=60):
    """
    Poll for new Himawari full-disk data.

    Himawari data is organized by date/time in the S3 bucket.
    """
    last_check = datetime.utcnow() - timedelta(minutes=15)

    while True:
        now = datetime.utcnow()
        # Check for data from last check time
        date_prefix = now.strftime('AHI-L1b-FLDK/%Y/%m/%d/')

        try:
            response = s3.list_objects_v2(
                Bucket=HIMAWARI_BUCKET,
                Prefix=date_prefix,
                MaxKeys=100
            )

            for obj in response.get('Contents', []):
                key = obj['Key']
                modified = obj['LastModified'].replace(tzinfo=None)

                if modified > last_check:
                    # New data available
                    if 'B07' in key:  # MIR band for fire detection
                        print(f"New fire-relevant data: {key} (modified: {modified})")
                        # Process the data...

        except Exception as e:
            print(f"Error polling: {e}")

        last_check = now
        time.sleep(check_interval_seconds)
```

## 4. Copernicus Data Space Query

### Sentinel-3 SLSTR FRP Query

```python
"""
Query Copernicus Data Space for Sentinel-3 SLSTR Fire Radiative Power products.
Requires: requests, oauthlib
"""

import requests
from datetime import datetime, timedelta

class CopernicusClient:
    TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    STAC_URL = "https://catalogue.dataspace.copernicus.eu/stac"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.access_token = None

    def authenticate(self):
        """Get access token."""
        data = {
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
            'client_id': 'cdse-public',
        }
        response = requests.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        self.access_token = response.json()['access_token']

    def search_slstr_frp(self, start_date, end_date,
                         bbox=[148, -37, 154, -28]):
        """
        Search for Sentinel-3 SLSTR FRP products over NSW.

        Args:
            start_date: str, ISO format
            end_date: str, ISO format
            bbox: [west, south, east, north]
        """
        if not self.access_token:
            self.authenticate()

        params = {
            'collections': ['SENTINEL-3'],
            'datetime': f"{start_date}/{end_date}",
            'bbox': bbox,
            'limit': 100,
        }

        headers = {'Authorization': f'Bearer {self.access_token}'}

        response = requests.get(
            f"{self.STAC_URL}/search",
            params=params,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    def search_sentinel2(self, start_date, end_date,
                         bbox=[148, -37, 154, -28]):
        """Search for Sentinel-2 products over NSW."""
        if not self.access_token:
            self.authenticate()

        params = {
            'collections': ['SENTINEL-2'],
            'datetime': f"{start_date}/{end_date}",
            'bbox': bbox,
            'limit': 100,
        }

        headers = {'Authorization': f'Bearer {self.access_token}'}

        response = requests.get(
            f"{self.STAC_URL}/search",
            params=params,
            headers=headers
        )
        response.raise_for_status()
        return response.json()
```

## 5. DEA Hotspots Integration

```python
"""
Query Digital Earth Australia Hotspots for fire detections.
No registration required.
"""

import requests
from datetime import datetime

DEA_HOTSPOTS_WFS = "https://hotspots.dea.ga.gov.au/geoserver/public/wfs"

def get_dea_hotspots(hours_back=1,
                     bbox='148,-37,154,-28',
                     max_features=1000):
    """
    Query DEA Hotspots WFS for recent fire detections in NSW.

    Returns GeoJSON features.
    """
    params = {
        'service': 'WFS',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeName': 'public:hotspot_current',
        'outputFormat': 'application/json',
        'bbox': bbox,
        'maxFeatures': max_features,
        'srsName': 'EPSG:4326',
    }

    response = requests.get(DEA_HOTSPOTS_WFS, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

if __name__ == '__main__':
    hotspots = get_dea_hotspots()
    features = hotspots.get('features', [])
    print(f"Found {len(features)} hotspots in NSW")
    for f in features[:5]:
        props = f.get('properties', {})
        coords = f.get('geometry', {}).get('coordinates', [])
        print(f"  {coords}: confidence={props.get('confidence')}, "
              f"satellite={props.get('satellite')}, "
              f"datetime={props.get('datetime')}")
```

## 6. Multi-Source Fire Monitoring System

### Integrated Monitor

```python
"""
Unified fire monitoring system that integrates multiple satellite data sources.
This is the top-level orchestrator for the competition.
"""

import threading
import queue
import time
from datetime import datetime

class FireMonitor:
    def __init__(self, firms_key, copernicus_user=None, copernicus_pass=None):
        self.alert_queue = queue.Queue()
        self.firms_key = firms_key
        self.running = False

        # Track known fires to avoid duplicate alerts
        self.known_fires = {}

    def start(self):
        """Start all monitoring threads."""
        self.running = True

        # Thread 1: Poll FIRMS for geostationary fire detections (Himawari)
        t1 = threading.Thread(target=self._poll_firms_geo, daemon=True)
        t1.start()

        # Thread 2: Poll FIRMS for VIIRS/MODIS fire detections
        t2 = threading.Thread(target=self._poll_firms_leo, daemon=True)
        t2.start()

        # Thread 3: Poll DEA Hotspots
        t3 = threading.Thread(target=self._poll_dea, daemon=True)
        t3.start()

        # Thread 4: Process alerts
        t4 = threading.Thread(target=self._process_alerts, daemon=True)
        t4.start()

        print("Fire monitoring started. Ctrl+C to stop.")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            print("Monitoring stopped.")

    def _poll_firms_geo(self):
        """Poll FIRMS for geostationary (Himawari) fire detections every 2 minutes."""
        client = FIRMSClient(self.firms_key)
        while self.running:
            try:
                fires = client.get_active_fires(source='H09_NRT', days=1)
                for fire in fires:
                    self.alert_queue.put({
                        'source': 'FIRMS_Himawari',
                        'type': 'geostationary',
                        'data': fire,
                        'timestamp': datetime.utcnow().isoformat()
                    })
            except Exception as e:
                print(f"FIRMS GEO error: {e}")
            time.sleep(120)  # 2-minute polling

    def _poll_firms_leo(self):
        """Poll FIRMS for VIIRS/MODIS detections every 5 minutes."""
        client = FIRMSClient(self.firms_key)
        sources = ['VIIRS_SNPP_NRT', 'VIIRS_NOAA20_NRT', 'VIIRS_NOAA21_NRT', 'MODIS_NRT']
        while self.running:
            for source in sources:
                try:
                    fires = client.get_active_fires(source=source, days=1)
                    for fire in fires:
                        self.alert_queue.put({
                            'source': f'FIRMS_{source}',
                            'type': 'polar',
                            'data': fire,
                            'timestamp': datetime.utcnow().isoformat()
                        })
                except Exception as e:
                    print(f"FIRMS LEO error ({source}): {e}")
            time.sleep(300)  # 5-minute polling

    def _poll_dea(self):
        """Poll DEA Hotspots every 5 minutes."""
        while self.running:
            try:
                hotspots = get_dea_hotspots()
                for feature in hotspots.get('features', []):
                    self.alert_queue.put({
                        'source': 'DEA_Hotspots',
                        'type': 'aggregated',
                        'data': feature,
                        'timestamp': datetime.utcnow().isoformat()
                    })
            except Exception as e:
                print(f"DEA error: {e}")
            time.sleep(300)

    def _process_alerts(self):
        """Process incoming fire alerts, deduplicate, and emit notifications."""
        while self.running:
            try:
                alert = self.alert_queue.get(timeout=1)
                fire_id = self._make_fire_id(alert)

                if fire_id not in self.known_fires:
                    self.known_fires[fire_id] = alert
                    self._emit_alert(alert)
                else:
                    # Update existing fire with new observation
                    self.known_fires[fire_id]['last_update'] = alert['timestamp']

            except queue.Empty:
                continue

    def _make_fire_id(self, alert):
        """Create a unique ID for deduplication (cluster nearby detections)."""
        data = alert.get('data', {})
        if isinstance(data, dict):
            lat = float(data.get('latitude', data.get('properties', {}).get('latitude', 0)))
            lon = float(data.get('longitude', data.get('properties', {}).get('longitude', 0)))
        else:
            return str(hash(str(data)))

        # Round to ~1km grid for deduplication
        lat_grid = round(lat * 100) / 100
        lon_grid = round(lon * 100) / 100
        return f"{lat_grid},{lon_grid}"

    def _emit_alert(self, alert):
        """Emit a fire alert (webhook, log, etc)."""
        print(f"FIRE ALERT: source={alert['source']}, "
              f"timestamp={alert['timestamp']}, "
              f"data={alert.get('data', {})}")


if __name__ == '__main__':
    monitor = FireMonitor(firms_key='YOUR_MAP_KEY')
    monitor.start()
```

## 7. Overpass-Aware Detection Scheduler

```python
"""
Schedule fire detection processing based on predicted satellite overpasses.
Ensures readiness for data arrival from each satellite pass.
"""

import json
from datetime import datetime, timedelta
from pyorbital.orbital import Orbital

class OverpassScheduler:
    def __init__(self, schedule_file=None):
        self.schedule = []
        if schedule_file:
            with open(schedule_file) as f:
                self.schedule = json.load(f)

    def get_next_overpass(self, satellite=None, after=None):
        """Get the next overpass, optionally filtered by satellite."""
        if after is None:
            after = datetime.utcnow().isoformat()

        for p in self.schedule:
            if p['max_alt_utc'] > after:
                if satellite is None or p['satellite'] == satellite:
                    return p
        return None

    def get_upcoming(self, hours=6, satellite=None):
        """Get all overpasses in the next N hours."""
        now = datetime.utcnow()
        cutoff = (now + timedelta(hours=hours)).isoformat()
        now_str = now.isoformat()

        return [
            p for p in self.schedule
            if p['max_alt_utc'] > now_str and p['max_alt_utc'] < cutoff
            and (satellite is None or p['satellite'] == satellite)
        ]

    def time_to_next_viirs(self):
        """How long until the next VIIRS overpass?"""
        now = datetime.utcnow()
        for p in self.schedule:
            if p['sensor'] == 'VIIRS' and p['max_alt_utc'] > now.isoformat():
                next_time = datetime.fromisoformat(p['max_alt_utc'])
                delta = next_time - now
                return delta, p
        return None, None
```
