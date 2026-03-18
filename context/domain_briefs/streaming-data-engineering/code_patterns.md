# Code Patterns: Python/boto3 for Satellite Data Streaming

## Scope

Working code patterns for subscribing to NOAA SNS topics, processing SQS messages, downloading and parsing satellite data, and calling the FIRMS API. All Python 3.11+ with boto3.

---

## 1. Subscribe SQS Queue to NOAA SNS Topic

This must run once (or in your IaC). Creates an SQS queue and subscribes it to NOAA's cross-account SNS topic.

```python
import boto3
import json

sqs = boto3.client('sqs', region_name='us-east-1')
sns = boto3.client('sns', region_name='us-east-1')

# Create the SQS queue
queue_response = sqs.create_queue(
    QueueName='himawari9-raw-notifications',
    Attributes={
        'VisibilityTimeout': '60',
        'MessageRetentionPeriod': '345600',  # 4 days
        'ReceiveMessageWaitTimeSeconds': '20',  # long polling
    }
)
queue_url = queue_response['QueueUrl']

# Get the queue ARN
queue_attrs = sqs.get_queue_attributes(
    QueueUrl=queue_url,
    AttributeNames=['QueueArn']
)
queue_arn = queue_attrs['Attributes']['QueueArn']

# Set queue policy to allow NOAA's SNS topic to send messages
# This is the critical cross-account permission
noaa_sns_arn = 'arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject'

policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "AllowNOAASNS",
        "Effect": "Allow",
        "Principal": {"Service": "sns.amazonaws.com"},
        "Action": "SQS:SendMessage",
        "Resource": queue_arn,
        "Condition": {
            "ArnEquals": {
                "aws:SourceArn": noaa_sns_arn
            }
        }
    }]
}

sqs.set_queue_attributes(
    QueueUrl=queue_url,
    Attributes={'Policy': json.dumps(policy)}
)

# Subscribe the SQS queue to the NOAA SNS topic
sns.subscribe(
    TopicArn=noaa_sns_arn,
    Protocol='sqs',
    Endpoint=queue_arn,
)

print(f"Queue {queue_url} subscribed to {noaa_sns_arn}")
```

**Important**: After subscribing, the subscription may need confirmation. For SQS protocol, AWS auto-confirms if the queue policy allows it. Verify in the SNS console that the subscription status is "Confirmed".

### Create All NOAA Subscriptions

```python
NOAA_TOPICS = {
    'himawari9': 'arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject',
    'himawari8': 'arn:aws:sns:us-east-1:123901341784:NewHimawari8Object',
    'goes19':    'arn:aws:sns:us-east-1:123901341784:NewGOES19Object',
    'goes18':    'arn:aws:sns:us-east-1:123901341784:NewGOES18Object',
    'noaa20':    'arn:aws:sns:us-east-1:709902155096:NewNOAA20Object',
    'noaa21':    'arn:aws:sns:us-east-1:709902155096:NewNOAA21Object',
    'snpp':      'arn:aws:sns:us-east-1:709902155096:NewSNPPObject',
}
```

---

## 2. SQS Message Parser (Triple-Nested JSON)

When NOAA S3 puts an object, the notification flows through SNS -> SQS, creating three layers of JSON wrapping.

```python
import json
from dataclasses import dataclass
from typing import Optional


@dataclass
class S3ObjectEvent:
    bucket: str
    key: str
    size: int
    event_time: str
    region: str


def parse_noaa_sqs_message(sqs_record: dict) -> list[S3ObjectEvent]:
    """Parse a single SQS record containing an SNS-wrapped S3 event.

    SQS record -> SNS message body -> S3 event Records array.
    Returns list because one SNS message can contain multiple S3 events.
    """
    # Layer 1: SQS body is a JSON string containing the SNS message
    sns_message = json.loads(sqs_record['body'])

    # Layer 2: SNS 'Message' field is a JSON string containing the S3 event
    # Handle both direct S3 notifications and SNS-wrapped ones
    if 'Message' in sns_message:
        s3_event = json.loads(sns_message['Message'])
    else:
        s3_event = sns_message

    # Layer 3: S3 event contains a 'Records' array
    events = []
    for record in s3_event.get('Records', []):
        s3_info = record.get('s3', {})
        bucket_name = s3_info.get('bucket', {}).get('name', '')
        object_key = s3_info.get('object', {}).get('key', '')
        object_size = s3_info.get('object', {}).get('size', 0)

        # URL-decode the key (spaces become '+', etc.)
        from urllib.parse import unquote_plus
        object_key = unquote_plus(object_key)

        events.append(S3ObjectEvent(
            bucket=bucket_name,
            key=object_key,
            size=object_size,
            event_time=record.get('eventTime', ''),
            region=record.get('awsRegion', 'us-east-1'),
        ))

    return events
```

---

## 3. Lambda Handler: Filter and Route

This Lambda sits between the raw SQS queue and the processing queue. It filters for relevant products and forwards only what matters.

```python
import json
import re
import os
import boto3

sqs = boto3.client('sqs')
PROCESSING_QUEUE_URL = os.environ['PROCESSING_QUEUE_URL']

# Patterns for fire-relevant Himawari data
# NSW is in segments 7-8 of the full disk
HIMAWARI_FIRE_PATTERN = re.compile(
    r'AHI-L1b-FLDK/\d{4}/\d{2}/\d{2}/\d{4}/'
    r'HS_H09_\d{8}_\d{4}_B(07|14|15)_.*_S(0[78]\d{2})\.DAT$'
)

# GOES fire products (if needed for non-Australia use)
GOES_FIRE_PATTERN = re.compile(
    r'ABI-L2-FDC[CFM]/'
)

# VIIRS active fire products
VIIRS_FIRE_PATTERN = re.compile(
    r'VIIRS.*AF.*\.nc$|VIIRS.*fire.*\.nc$',
    re.IGNORECASE
)


def lambda_handler(event, context):
    """Filter NOAA notifications, forward fire-relevant ones to processing queue."""
    forwarded = 0
    skipped = 0

    for sqs_record in event['Records']:
        try:
            s3_events = parse_noaa_sqs_message(sqs_record)

            for s3_event in s3_events:
                key = s3_event.key

                is_relevant = (
                    HIMAWARI_FIRE_PATTERN.search(key) or
                    GOES_FIRE_PATTERN.search(key) or
                    VIIRS_FIRE_PATTERN.search(key)
                )

                if is_relevant:
                    sqs.send_message(
                        QueueUrl=PROCESSING_QUEUE_URL,
                        MessageBody=json.dumps({
                            'bucket': s3_event.bucket,
                            'key': s3_event.key,
                            'size': s3_event.size,
                            'event_time': s3_event.event_time,
                            'source': _classify_source(s3_event.bucket),
                        }),
                    )
                    forwarded += 1
                else:
                    skipped += 1

        except Exception as e:
            print(f"Error parsing SQS record: {e}")
            # Don't raise -- let the message be deleted.
            # If you raise, SQS retries and it likely fails again.
            continue

    print(f"Forwarded: {forwarded}, Skipped: {skipped}")
    return {'statusCode': 200, 'forwarded': forwarded, 'skipped': skipped}


def _classify_source(bucket: str) -> str:
    if 'himawari' in bucket:
        return 'himawari'
    elif 'goes' in bucket:
        return 'goes'
    elif 'n20' in bucket or 'n21' in bucket or 'snpp' in bucket:
        return 'viirs'
    return 'unknown'
```

---

## 4. Download Satellite Data from NOAA S3

NOAA buckets are public. Use unsigned requests for fastest access.

```python
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import io

# Unsigned client -- no SigV4 overhead, works for public buckets
s3_unsigned = boto3.client(
    's3',
    region_name='us-east-1',
    config=Config(signature_version=UNSIGNED),
)

# Alternative: use s3fs for filesystem-like access
# import s3fs
# fs = s3fs.S3FileSystem(anon=True)


def download_to_memory(bucket: str, key: str) -> bytes:
    """Download an S3 object into memory. Fast for files <100MB."""
    response = s3_unsigned.get_object(Bucket=bucket, Key=key)
    return response['Body'].read()


def download_to_file(bucket: str, key: str, local_path: str) -> str:
    """Download an S3 object to local filesystem."""
    s3_unsigned.download_file(bucket, key, local_path)
    return local_path


def stream_netcdf(bucket: str, key: str):
    """Open a NetCDF file directly from S3 using xarray + h5netcdf.

    Requires: pip install xarray h5netcdf s3fs
    """
    import xarray as xr

    s3_path = f's3://{bucket}/{key}'
    ds = xr.open_dataset(
        s3_path,
        engine='h5netcdf',
        storage_options={'anon': True},
    )
    return ds
```

### Download Himawari HSD Data

Himawari data is in Himawari Standard Data (HSD) format, not NetCDF. Use the `satpy` library to read it:

```python
from satpy import Scene
import tempfile
import os


def read_himawari_hsd(bucket: str, keys: list[str]) -> 'Scene':
    """Download Himawari HSD files and read with satpy.

    keys: list of S3 keys for the segments/bands needed.
    """
    tmpdir = tempfile.mkdtemp()
    local_files = []

    for key in keys:
        filename = os.path.basename(key)
        local_path = os.path.join(tmpdir, filename)
        download_to_file(bucket, key, local_path)
        local_files.append(local_path)

    scn = Scene(filenames=local_files, reader='ahi_hsd')
    scn.load(['B07', 'B14', 'B15'])  # fire-relevant bands
    return scn
```

---

## 5. GOES ABI Fire Product Reader

```python
import xarray as xr
import numpy as np
from botocore import UNSIGNED
from botocore.config import Config
import boto3


def read_goes_fire_product(bucket: str, key: str) -> dict:
    """Read GOES ABI L2 FDC (Fire Detection Characterization) NetCDF.

    Returns dict with fire mask, temperature, area, FRP arrays.
    """
    # Download to memory
    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    response = s3.get_object(Bucket=bucket, Key=key)
    data = response['Body'].read()

    # Open with xarray from bytes
    import io
    ds = xr.open_dataset(io.BytesIO(data), engine='h5netcdf')

    result = {
        'fire_mask': ds['Mask'].values,         # Fire detection categories
        'fire_temp': ds['Temp'].values,          # Fire temperature (K)
        'fire_area': ds['Area'].values,          # Fire area (km^2)
        'fire_power': ds['Power'].values,        # Fire radiative power (MW)
        'lat': ds['goes_imager_projection'],     # Projection info
        'time_coverage_start': ds.attrs.get('time_coverage_start'),
        'time_coverage_end': ds.attrs.get('time_coverage_end'),
    }

    ds.close()
    return result


def list_fire_products(satellite: str, year: int, doy: int, hour: int) -> list[str]:
    """List available FDC products for a given time.

    satellite: 'goes18' or 'goes19'
    doy: day of year (1-366)
    hour: UTC hour (0-23)
    """
    bucket = f'noaa-{satellite}'
    prefix = f'ABI-L2-FDCF/{year}/{doy:03d}/{hour:02d}/'

    s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)

    keys = []
    for obj in response.get('Contents', []):
        keys.append(obj['Key'])
    return keys
```

---

## 6. FIRMS API Client

```python
import requests
from dataclasses import dataclass
from typing import Optional
import csv
import io


@dataclass
class FIRMSConfig:
    map_key: str
    base_url: str = 'https://firms.modaps.eosdis.nasa.gov/api'
    timeout: int = 30


@dataclass
class FireDetection:
    latitude: float
    longitude: float
    brightness: float  # bright_ti4 for VIIRS, brightness for MODIS
    scan: float
    track: float
    acq_date: str
    acq_time: str
    satellite: str
    confidence: str
    frp: float
    daynight: str


class FIRMSClient:
    """Client for NASA FIRMS active fire data API."""

    # NSW Australia bounding box
    NSW_BBOX = '148,-37,154,-28'

    SOURCES = {
        'viirs_noaa20_nrt': 'VIIRS_NOAA20_NRT',
        'viirs_noaa21_nrt': 'VIIRS_NOAA21_NRT',
        'viirs_snpp_nrt':   'VIIRS_SNPP_NRT',
        'modis_nrt':        'MODIS_NRT',
    }

    def __init__(self, config: FIRMSConfig):
        self.config = config
        self.session = requests.Session()

    def get_fires_area(
        self,
        source: str = 'VIIRS_NOAA20_NRT',
        bbox: str = NSW_BBOX,
        day_range: int = 1,
        date: Optional[str] = None,
    ) -> list[FireDetection]:
        """Fetch active fire detections for a bounding box.

        Args:
            source: data source key (e.g., VIIRS_NOAA20_NRT)
            bbox: 'west,south,east,north' coordinates
            day_range: 1-10 days of data
            date: optional YYYY-MM-DD for historical queries

        Returns:
            List of FireDetection objects
        """
        url = f'{self.config.base_url}/area/csv/{self.config.map_key}/{source}/{bbox}/{day_range}'
        if date:
            url += f'/{date}'

        response = self.session.get(url, timeout=self.config.timeout)
        response.raise_for_status()

        detections = []
        reader = csv.DictReader(io.StringIO(response.text))
        for row in reader:
            # VIIRS uses bright_ti4, MODIS uses brightness
            brightness_key = 'bright_ti4' if 'bright_ti4' in row else 'brightness'

            detections.append(FireDetection(
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
                brightness=float(row.get(brightness_key, 0)),
                scan=float(row.get('scan', 0)),
                track=float(row.get('track', 0)),
                acq_date=row.get('acq_date', ''),
                acq_time=row.get('acq_time', ''),
                satellite=row.get('satellite', ''),
                confidence=row.get('confidence', ''),
                frp=float(row.get('frp', 0)),
                daynight=row.get('daynight', ''),
            ))

        return detections

    def check_data_availability(self, source: str = 'VIIRS_NOAA20_NRT') -> dict:
        """Check which dates have data available."""
        url = f'{self.config.base_url}/data_availability/csv/{self.config.map_key}/{source}'
        response = self.session.get(url, timeout=self.config.timeout)
        response.raise_for_status()
        return response.text

    def poll_all_sources(self, bbox: str = NSW_BBOX) -> list[FireDetection]:
        """Poll all NRT sources for the latest fires."""
        all_detections = []
        for name, source in self.SOURCES.items():
            try:
                detections = self.get_fires_area(source=source, bbox=bbox, day_range=1)
                all_detections.extend(detections)
            except requests.RequestException as e:
                print(f"Failed to fetch {name}: {e}")
        return all_detections


# Usage:
# client = FIRMSClient(FIRMSConfig(map_key='your_32_char_key'))
# fires = client.get_fires_area(source='VIIRS_NOAA20_NRT', bbox='148,-37,154,-28')
```

---

## 7. Scheduled FIRMS Polling Lambda

```python
import json
import os
import hashlib
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

TABLE_NAME = os.environ.get('FIRMS_STATE_TABLE', 'firms-fire-detections')
ALERT_TOPIC = os.environ.get('ALERT_TOPIC_ARN', '')


def lambda_handler(event, context):
    """Scheduled Lambda (every 5 min) to poll FIRMS and emit new detections."""
    from firms_client import FIRMSClient, FIRMSConfig

    config = FIRMSConfig(map_key=os.environ['FIRMS_MAP_KEY'])
    client = FIRMSClient(config)
    table = dynamodb.Table(TABLE_NAME)

    fires = client.poll_all_sources(bbox='148,-37,154,-28')
    new_fires = []

    for fire in fires:
        # Create a unique hash for this detection
        fire_id = hashlib.sha256(
            f"{fire.latitude:.4f}:{fire.longitude:.4f}:{fire.acq_date}:{fire.acq_time}:{fire.satellite}".encode()
        ).hexdigest()[:16]

        # Try to write -- if it already exists, skip (idempotent)
        try:
            table.put_item(
                Item={
                    'fire_id': fire_id,
                    'latitude': str(fire.latitude),
                    'longitude': str(fire.longitude),
                    'brightness': str(fire.brightness),
                    'frp': str(fire.frp),
                    'confidence': fire.confidence,
                    'satellite': fire.satellite,
                    'acq_date': fire.acq_date,
                    'acq_time': fire.acq_time,
                    'daynight': fire.daynight,
                    'detected_at': datetime.utcnow().isoformat(),
                    'ttl': int(datetime.utcnow().timestamp()) + 86400,
                },
                ConditionExpression='attribute_not_exists(fire_id)',
            )
            new_fires.append(fire)
        except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
            pass  # Already seen

    # Alert on new fires
    if new_fires and ALERT_TOPIC:
        sns_client.publish(
            TopicArn=ALERT_TOPIC,
            Subject=f'FIRMS: {len(new_fires)} new fire detection(s) in NSW',
            Message=json.dumps([{
                'lat': f.latitude,
                'lon': f.longitude,
                'frp': f.frp,
                'confidence': f.confidence,
                'satellite': f.satellite,
                'time': f'{f.acq_date} {f.acq_time}',
            } for f in new_fires], indent=2),
        )

    return {'new_fires': len(new_fires), 'total_checked': len(fires)}
```

---

## 8. Scatter-Gather: Himawari Segment Assembly

```python
import boto3
import json
import os
import re
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sqs = boto3.client('sqs')

SEGMENT_TABLE = os.environ.get('SEGMENT_TABLE', 'himawari-segments')
PROCESSING_QUEUE = os.environ.get('PROCESSING_QUEUE_URL', '')

# NSW covers segments 7-8 in Himawari full disk (10 segments, north to south)
NSW_SEGMENTS = {'S0701', 'S0702', 'S0703', 'S0704',
                'S0801', 'S0802', 'S0803', 'S0804'}
# (exact segment IDs depend on the specific segmentation scheme;
#  verify with actual Himawari file listings)

REQUIRED_BANDS = {'B07', 'B14', 'B15'}


def lambda_handler(event, context):
    """Receives filtered Himawari notifications.
    Tracks segments in DynamoDB. When all NSW segments for a band-set arrive,
    triggers processing.
    """
    table = dynamodb.Table(SEGMENT_TABLE)

    for record in event['Records']:
        msg = json.loads(record['body'])
        key = msg['key']
        bucket = msg['bucket']

        # Parse the filename to extract observation time, band, segment
        # Example: HS_H09_20260415_0300_B07_R201_R20_S0701.DAT
        match = re.search(
            r'HS_H09_(\d{8})_(\d{4})_(B\d{2})_\w+_\w+_(S\d{4})\.DAT$',
            key
        )
        if not match:
            continue

        date_str, time_str, band, segment = match.groups()
        obs_key = f"{date_str}#{time_str}"  # e.g., "20260415#0300"

        # Only track segments we care about
        if segment[:4] not in {s[:4] for s in NSW_SEGMENTS}:
            continue
        if band not in REQUIRED_BANDS:
            continue

        # Record this segment
        segment_id = f"{band}#{segment}"
        table.put_item(
            Item={
                'obs_key': obs_key,
                'segment_id': segment_id,
                's3_bucket': bucket,
                's3_key': key,
                'received_at': datetime.utcnow().isoformat(),
                'ttl': int(datetime.utcnow().timestamp()) + 3600,  # 1 hour TTL
            }
        )

        # Check if all required segments have arrived
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('obs_key').eq(obs_key),
        )
        received = {item['segment_id'] for item in response['Items']}

        # Build expected set: each band x each NSW segment
        expected = {f"{b}#{s}" for b in REQUIRED_BANDS for s in NSW_SEGMENTS}

        if expected.issubset(received):
            # All segments arrived -- trigger processing
            file_manifest = {
                item['segment_id']: {
                    'bucket': item['s3_bucket'],
                    'key': item['s3_key'],
                }
                for item in response['Items']
                if item['segment_id'] in expected
            }

            sqs.send_message(
                QueueUrl=PROCESSING_QUEUE,
                MessageBody=json.dumps({
                    'observation': obs_key,
                    'files': file_manifest,
                    'trigger_time': datetime.utcnow().isoformat(),
                }),
            )
            print(f"Triggered processing for observation {obs_key}")
```

---

## 9. Async S3 Downloads with asyncio + aioboto3

For downloading multiple files concurrently (e.g., multiple Himawari segments):

```python
import asyncio
import aioboto3
from botocore import UNSIGNED
from botocore.config import Config


async def download_files_async(
    files: list[dict],  # [{'bucket': ..., 'key': ..., 'local_path': ...}]
    max_concurrent: int = 10,
) -> list[str]:
    """Download multiple S3 files concurrently.

    Returns list of local file paths.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    session = aioboto3.Session()
    async with session.client(
        's3',
        region_name='us-east-1',
        config=Config(signature_version=UNSIGNED),
    ) as s3:
        async def download_one(file_info):
            async with semaphore:
                response = await s3.get_object(
                    Bucket=file_info['bucket'],
                    Key=file_info['key'],
                )
                data = await response['Body'].read()
                with open(file_info['local_path'], 'wb') as f:
                    f.write(data)
                return file_info['local_path']

        tasks = [download_one(f) for f in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for errors
    paths = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Download failed: {result}")
        else:
            paths.append(result)

    return paths


# Usage in Lambda (Python 3.11+ has built-in asyncio support):
# paths = asyncio.run(download_files_async(file_list))
```

---

## 10. Infrastructure as Code (CDK Sketch)

```python
from aws_cdk import (
    Stack, Duration,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_lambda as lambda_,
    aws_lambda_event_sources as events,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class SatelliteIngestionStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # Dead letter queue
        dlq = sqs.Queue(self, 'DLQ',
            queue_name='satellite-ingestion-dlq',
            retention_period=Duration.days(14),
        )

        # Raw notification queue (receives ALL NOAA notifications)
        raw_queue = sqs.Queue(self, 'RawQueue',
            queue_name='himawari9-raw-notifications',
            visibility_timeout=Duration.seconds(60),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=4,
                queue=dlq,
            ),
        )

        # Processing queue (receives only fire-relevant notifications)
        processing_queue = sqs.Queue(self, 'ProcessingQueue',
            queue_name='fire-processing-queue',
            visibility_timeout=Duration.seconds(120),
        )

        # Subscribe to NOAA SNS topic (cross-account)
        noaa_topic = sns.Topic.from_topic_arn(
            self, 'NoaaHimawari9Topic',
            'arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject',
        )
        noaa_topic.add_subscription(subs.SqsSubscription(raw_queue))

        # Filter Lambda
        filter_fn = lambda_.Function(self, 'FilterFunction',
            function_name='satellite-filter',
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler='filter.lambda_handler',
            code=lambda_.Code.from_asset('lambda/filter'),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment={
                'PROCESSING_QUEUE_URL': processing_queue.queue_url,
            },
        )
        processing_queue.grant_send_messages(filter_fn)

        # Wire SQS -> Lambda with small batch for low latency
        filter_fn.add_event_source(events.SqsEventSource(
            raw_queue,
            batch_size=5,
            max_batching_window=Duration.seconds(0),
        ))

        # Segment tracking table
        segment_table = dynamodb.Table(self, 'SegmentTable',
            table_name='himawari-segments',
            partition_key=dynamodb.Attribute(
                name='obs_key', type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(
                name='segment_id', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute='ttl',
        )
```

---

## 11. Copernicus STAC Client

```python
import requests
from datetime import datetime, timedelta


class CopernicusSTACClient:
    """Query Copernicus Data Space STAC API for Sentinel-3 FRP products."""

    BASE_URL = 'https://stac.dataspace.copernicus.eu/v1'

    def __init__(self, access_token: str = None):
        self.session = requests.Session()
        if access_token:
            self.session.headers['Authorization'] = f'Bearer {access_token}'

    def search_sentinel3_frp(
        self,
        bbox: list[float] = [148, -37, 154, -28],  # NSW
        start_date: str = None,
        end_date: str = None,
        limit: int = 50,
    ) -> dict:
        """Search for Sentinel-3 SLSTR FRP products over a region."""
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
        if not end_date:
            end_date = datetime.utcnow().strftime('%Y-%m-%dT23:59:59Z')

        payload = {
            'collections': ['sentinel-3-slstr-frp'],
            'bbox': bbox,
            'datetime': f'{start_date}/{end_date}',
            'limit': limit,
        }

        response = self.session.post(
            f'{self.BASE_URL}/search',
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def list_collections(self, query: str = 'sentinel-3') -> list:
        """List available STAC collections matching a query."""
        response = self.session.get(
            f'{self.BASE_URL}/collections',
            params={'q': query},
        )
        response.raise_for_status()
        data = response.json()
        return [(c['id'], c.get('title', '')) for c in data.get('collections', [])]
```
