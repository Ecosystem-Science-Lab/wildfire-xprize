# Pitfalls: What Breaks in Satellite Data Streaming

## Scope

Concrete failure modes, latency traps, ordering issues, throttling limits, and operational hazards when building a real-time satellite data ingestion pipeline on AWS. Organized by where things go wrong.

---

## 1. SNS/SQS Subscription Pitfalls

### SNS Topic Protocol Restrictions

NOAA NODD SNS topics only support **SQS and Lambda** protocols. You cannot use HTTP/HTTPS webhooks or email. If you try to subscribe with protocol `https`, it will be rejected.

### Cross-Account Subscription Confirmation

When subscribing your SQS queue to NOAA's SNS topic (different AWS account), the subscription requires confirmation. For SQS protocol, this is auto-confirmed IF your queue policy explicitly allows the NOAA SNS topic ARN to send messages. If you forget the queue policy, the subscription will show as "Pending confirmation" forever and you will receive zero messages with no error.

**Check**: After subscribing, verify in the SNS console (or via `aws sns list-subscriptions-by-topic`) that the subscription status is `Confirmed`, not `PendingConfirmation`.

### Different AWS Accounts for Different Datasets

GOES and Himawari SNS topics are in AWS account `123901341784`. JPSS topics are in account `709902155096`. Your SQS queue policy must allow BOTH accounts if you subscribe to both. A single `aws:SourceArn` condition won't work -- use a list:

```json
"Condition": {
    "ArnEquals": {
        "aws:SourceArn": [
            "arn:aws:sns:us-east-1:123901341784:NewHimawariNineObject",
            "arn:aws:sns:us-east-1:709902155096:NewNOAA20Object"
        ]
    }
}
```

Or use separate queues per source (recommended).

### SNS Message Size Limit

SNS messages are limited to 256 KB. S3 event notifications are small (~1-2 KB), so this shouldn't be an issue, but if you add large message attributes, you could hit it.

---

## 2. Latency Traps

### The 24-Second GOES Trap

GOES end-to-end latency (observation to S3) is ~24 seconds. This is excellent. But Himawari's path through JMA adds significant latency -- likely **2-5 minutes**. If your latency budget assumes GOES-like performance for Himawari, you will be disappointed.

### Lambda Cold Starts

Python Lambda cold starts are 100-500ms for simple functions but can reach **3-5 seconds** for functions with heavy dependencies (numpy, xarray, netCDF4). This matters when your total processing budget is <10 seconds.

**Mitigations**:
- Use Lambda provisioned concurrency ($0.015/hr per slot) for the filter function
- Pre-package dependencies in a Lambda layer (avoid downloading at cold start)
- Use slim dependencies: `h5py` instead of `xarray` for simple NetCDF reads
- For the heavy processing function, use ECS Fargate (always warm) not Lambda

### SQS Polling Latency

SQS uses **long polling** (up to 20 seconds). But there's additional latency:
- Lambda event source mapping polls SQS. With default configuration, there's **1-5 seconds** from message arrival to Lambda invocation.
- Provisioned mode reduces this to **near-zero** but costs more.
- Setting `MaximumBatchingWindow=0` and `BatchSize=1` minimizes wait-for-batch delay.

### S3 First-Byte Latency

Same-region S3 reads have ~10-50ms first-byte latency. But:
- Cross-region reads (if you accidentally run in ap-southeast-2 instead of us-east-1) add **50-200ms**
- Large files (100MB+ NetCDF) take **1-3 seconds** to fully download even in-region
- S3 is eventually consistent for LIST operations (though strongly consistent for GET/PUT since 2020)

### DNS Resolution

First S3 request in a Lambda invocation incurs DNS resolution (~10-50ms). Subsequent requests reuse the connection. Keep the S3 client alive across invocations (module-level initialization).

---

## 3. Data Format Pitfalls

### Himawari HSD vs NetCDF

Himawari data on AWS (NODD) is in **Himawari Standard Data (HSD)** format, NOT NetCDF. This is a proprietary binary format. You cannot open it with `xarray.open_dataset()` directly.

**Solutions**:
- Use `satpy` library with `ahi_hsd` reader
- Use the `pyhimawari` or `himawari_api` packages
- Manually parse the binary format (not recommended)

`satpy` dependency is heavy (~100+ transitive dependencies). This pushes you toward ECS for Himawari processing rather than Lambda.

### GOES NetCDF Projection

GOES ABI data uses the **GOES-R Fixed Grid** projection, not lat/lon. The NetCDF file contains projection parameters but not pre-computed lat/lon arrays. You must compute lat/lon from the projection:

```python
# This is NOT trivial -- requires understanding of geostationary projection
# Use satpy, pyresample, or the goes_imager_projection metadata
```

If you just read the data naively, you'll get array indices, not geographic coordinates.

### URL-Encoded S3 Keys

S3 event notifications URL-encode object keys. A key like `AHI-L1b-FLDK/2026/04/15/0300/HS_H09...` becomes `AHI-L1b-FLDK%2F2026%2F04%2F15%2F0300%2FHS_H09...` in the notification. Always `urllib.parse.unquote_plus()` before using the key for S3 API calls.

### NetCDF Fill Values

NetCDF fire products use fill values (typically `-1` or `NaN`) for pixels with no fire detection. If you don't mask these, you'll get false positives or divide-by-zero errors. Always check the `_FillValue` attribute.

---

## 4. Throttling and Rate Limits

### FIRMS API Limits

- **5,000 transactions per 10-minute interval**
- Large bounding boxes or many days count as multiple transactions
- If you exceed the limit, you get HTTP 429 (or sometimes 500)
- **No official retry-after header** -- back off exponentially
- Contact FIRMS for higher limits if needed

### S3 Request Limits

S3 supports 5,500 GET requests per second per prefix. NOAA buckets serve thousands of users simultaneously. While you're unlikely to hit this yourself, NOAA could hit it, causing 503 SlowDown errors.

**Mitigation**: Implement retry with exponential backoff. boto3's default retry config handles this, but increase `max_attempts`:

```python
from botocore.config import Config
config = Config(retries={'max_attempts': 5, 'mode': 'adaptive'})
```

### SNS Delivery Throttling

SNS can throttle delivery to SQS if the queue is overwhelmed. This is rare but can happen during data bursts.

### Lambda Concurrency Limits

Default Lambda concurrent execution limit is **1,000 per region**. If you're processing thousands of Himawari segments simultaneously, you can hit this. Set `ReservedConcurrentExecutions` on your processing function to protect other functions.

### SQS Batch Receive Limit

`ReceiveMessage` returns at most **10 messages** per call. If you need higher throughput, the Lambda event source mapping handles this internally with multiple pollers.

---

## 5. Ordering and Consistency Issues

### SNS Does Not Guarantee Order

Messages may arrive out of order. Segment S0801 might arrive before S0701. Your scatter-gather pattern must handle this.

### SQS Standard Does Not Guarantee Order

Same. And it provides **at-least-once delivery** -- you may receive the same message twice. Your processing must be idempotent.

### NOAA Data Gaps

NOAA satellite data has occasional gaps:
- Satellite maneuvers (eclipse season for geostationary)
- Ground system maintenance
- Data processing failures
- Network issues between JMA and NOAA (for Himawari)

FIRMS has a "Missing Data" API endpoint to check for known gaps:
```
https://firms.modaps.eosdis.nasa.gov/api/missing_data/csv/{MAP_KEY}/{SOURCE}
```

### Late-Arriving Data

Data sometimes arrives minutes or hours late. If you maintain a temporal sliding window for anomaly detection, late data can corrupt your background model unless you handle it explicitly (insert into the correct temporal position, not the end).

### S3 Eventual Consistency for LIST

Although S3 is strongly consistent for GET/PUT/DELETE since 2020, `LIST` operations can still show stale results briefly. If you list a prefix to find the latest file, you might miss a recently written file. Prefer SNS notifications over polling-by-listing.

---

## 6. Deployment and Operational Pitfalls

### Region Mismatch

ALL NOAA NODD data and SNS topics are in **us-east-1**. If you deploy your SQS/Lambda in any other region:
- Cross-region SNS->SQS delivery adds latency
- Cross-region S3 reads are slower and cost money (data transfer charges)
- Some cross-region SNS->SQS configurations may not work at all

**Deploy everything in us-east-1**, even though the competition is in Australia. Cross-region latency for delivering alerts from us-east-1 to Australia (~200ms) is negligible compared to satellite data latency.

### Lambda Package Size

Lambda has a 250MB unzipped deployment package limit (with layers). Scientific Python stacks (numpy + scipy + xarray + satpy + netCDF4) easily exceed this.

**Solutions**:
- Use Lambda container images (up to 10GB)
- Strip unnecessary files from packages (`__pycache__`, tests, docs)
- Use Lambda layers for large stable dependencies
- Move heavy processing to ECS Fargate

### DynamoDB Capacity for Segment Tracking

If using on-demand DynamoDB for segment tracking, each Himawari observation writes ~48 items (16 bands x ~3 segments per band relevant to NSW). At one observation every 10 minutes, that's ~288 writes/hour. Negligible cost, but if you accidentally track ALL segments for ALL bands (160 items per observation), it adds up.

### S3 Storage Classes

NOAA moves older data from S3 Standard to Infrequent Access after 30 days. If you're accessing historical data for background model training, you'll pay IA retrieval fees. These are small but can surprise you.

### CloudWatch Logging Costs

Lambda functions that log every SQS message can generate significant CloudWatch Logs volume. At ~41,000 Himawari notifications/day, even 1 KB per log entry = 40 MB/day = ~$2/month just for logs. Not catastrophic, but log selectively.

---

## 7. Data Quality Pitfalls

### Himawari Segment Ordering

Himawari full disk is split into 10 segments (north to south). The segment numbering determines which geographic area is covered. If you get the segment-to-latitude mapping wrong, you'll process the wrong part of the globe. Verify with actual data.

### GOES Fire Product False Positives

The GOES ABI FDC product has known false positive sources:
- Sun glint (especially over water)
- Hot industrial sites
- Desert surfaces during peak heating
- Volcanic activity

The `Mask` variable in the FDC NetCDF has bit flags for these. Don't treat every non-zero fire mask as a fire.

### VIIRS South Atlantic Anomaly

VIIRS removes low-confidence nighttime detections in the South Atlantic Anomaly zone (11E-110W, 7N-55S) due to detector noise from radiation. NSW is outside this zone, so it shouldn't affect the competition, but be aware if testing globally.

### FIRMS Confidence Levels

FIRMS VIIRS confidence is categorical (`low`, `nominal`, `high`), not numeric. MODIS confidence is numeric (0-100). Don't compare them directly. For alerting, consider only `nominal` and `high` confidence VIIRS detections.

### Temporal Aliasing

Himawari scans the full disk over 10 minutes. The observation time varies by latitude -- the timestamp in the filename is the scan START time. The actual observation of NSW (mid-latitudes in the southern hemisphere) happens several minutes into the scan. If you're correlating with LEO satellite overpasses, account for this.

---

## 8. Cost Surprises

### Data Transfer Costs

- S3 reads in the same region: **free**
- S3 reads from a different region: **$0.02/GB**
- At 10 TB/day of satellite data, cross-region reads cost **$200/day**

### NAT Gateway Costs

If your Lambda/ECS runs in a VPC (e.g., for database access), you need a NAT Gateway for S3 access. NAT Gateway charges **$0.045/GB processed**. 10 TB/day = **$450/day**.

**Solution**: Use VPC endpoints for S3 (free for traffic, $0.01/hr for the endpoint) instead of NAT Gateway.

### CloudWatch Metrics

Custom CloudWatch metrics cost $0.30/metric/month for the first 10,000 metrics. If you create per-band, per-segment, per-observation metrics, this adds up fast. Aggregate your metrics.

---

## 9. Testing Pitfalls

### No NOAA Sandbox

NOAA doesn't provide a sandbox or test SNS topic. To test your subscription:
1. Subscribe to the real topic
2. Wait for real data to flow (it's continuous)
3. Process it
4. There's no way to replay old notifications

**For development**: Download sample files from S3 manually and test your processing pipeline locally. Mock the SQS messages.

### FIRMS API Testing

The FIRMS API is rate-limited even for testing. Cache responses locally during development. The MAP_KEY is free but shared across your team.

### Himawari HSD Test Data

Finding Himawari HSD sample data for unit tests is difficult. The easiest approach is to download a few files from `s3://noaa-himawari9/` and include them in your test fixtures (they're typically 1-20 MB each).
