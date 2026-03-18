# Event-Driven Processing Patterns and Queue Management

## Scope

Algorithms and patterns for event-driven satellite data ingestion, queue management, backpressure handling, and stream processing. Focused on the operational patterns needed to reliably process NOAA satellite data at sub-10-second latency.

---

## 1. SNS Fan-Out with Filtered SQS Routing

### Problem

NOAA SNS topics fire on EVERY new object in the bucket. The `noaa-himawari9` bucket receives ~41,000 files/day across all products, bands, and regions. We only care about a subset (e.g., AHI-L1b-FLDK bands B07, B14, B15).

### Pattern: SNS Subscription Filter Policy

SNS supports message attribute-based filtering at the subscription level, which prevents irrelevant messages from ever reaching your SQS queue:

```json
{
  "FilterPolicy": {
    "s3:prefix": [{"prefix": "AHI-L1b-FLDK"}]
  },
  "FilterPolicyScope": "MessageBody"
}
```

However, NOAA NODD SNS notifications may not include message attributes that allow fine-grained filtering. In practice, you likely need to accept all messages and filter in the first Lambda.

### Pattern: Two-Stage Lambda Filter

```
SNS → SQS (raw) → Lambda (filter) → SQS (filtered) → Lambda (process)
```

Stage 1 Lambda (~128MB, <500ms):
1. Parse the triple-nested JSON (SQS envelope → SNS message → S3 event)
2. Extract the S3 object key
3. Check if key matches desired products (regex on key path)
4. If match: forward to processing SQS queue
5. If no match: delete message, do nothing

Stage 2 Lambda or ECS (2GB+, ~5-10s):
1. Download the relevant file from S3
2. Run fire detection algorithm
3. Emit results

This keeps Stage 1 cheap and fast, and only Stage 2 does expensive work.

---

## 2. Backpressure and Flow Control

### The Problem

Satellite data arrives in bursts. A Himawari full disk scan generates ~160 files (10 segments x 16 bands) arriving within seconds. If processing can't keep up, the queue grows, and latency degrades.

### Pattern: Queue Depth-Based Auto-Scaling

Monitor SQS `ApproximateNumberOfMessagesVisible` (visible queue depth) and scale processing:

```
Queue Depth     Action
< 10            Min capacity (1 ECS task or Lambda provisioned concurrency = 5)
10 - 50         Scale up linearly
50 - 200        Aggressive scale up
> 200           Max capacity + alert
```

For Lambda, this is handled automatically by the event source mapping, but you control the bounds:
- `MaximumConcurrency` on Lambda event source mapping caps how many concurrent invocations
- Provisioned mode `MinimumPollers` / `MaximumPollers` controls scaling speed

For ECS, use Application Auto Scaling with a custom CloudWatch metric target:
- Target tracking: `ApproximateNumberOfMessagesVisible / NumberOfRunningTasks < 5`

### Pattern: Prioritized Processing

Not all satellite data is equally time-sensitive. Use separate SQS queues with different processing priorities:

```
HIGH PRIORITY:  Himawari-9 FLDK B07 (3.9um fire band)  → fast path
MEDIUM:         Himawari-9 FLDK B14, B15 (context bands) → normal path
LOW:            VIIRS bulk products, FIRMS polling        → batch path
```

The fast path uses provisioned concurrency (always warm). The batch path uses standard scaling.

### Pattern: Adaptive Batch Size

When the system is caught up (queue near-empty), use batch_size=1 for minimum latency. When falling behind, increase batch_size to process more files per invocation:

```python
# In the Lambda event source mapping config, use small batch for latency
# But if you detect backlog via monitoring, temporarily update:
lambda_client.update_event_source_mapping(
    UUID=esm_uuid,
    BatchSize=10,           # up from 1
    MaximumBatchingWindow=5  # allow 5-sec batching
)
```

---

## 3. Exactly-Once vs At-Least-Once Processing

### SQS Guarantees

Standard SQS provides **at-least-once delivery**. Messages can be delivered more than once, especially during high throughput. FIFO SQS provides exactly-once but has lower throughput (3,000 msg/sec with batching).

For satellite data processing:
- **Use Standard SQS** (not FIFO) for throughput
- **Make processing idempotent** -- running fire detection on the same file twice should produce the same result
- **Track processed files** in DynamoDB to avoid duplicate alerts

### Idempotency Pattern

```python
# Before processing, check if we've already handled this S3 object
table = dynamodb.Table('processed_objects')
try:
    table.put_item(
        Item={'s3_key': s3_key, 'processed_at': now, 'ttl': now + 86400},
        ConditionExpression='attribute_not_exists(s3_key)'
    )
except ConditionalCheckFailedException:
    # Already processed, skip
    return
```

---

## 4. File Assembly for Multi-Segment Data

### The Problem

Himawari full disk data arrives as 10 separate segment files per band. Fire detection needs the complete image (or at least the segments covering NSW).

### Pattern: Scatter-Gather with DynamoDB Coordination

```
SNS notification for segment 1 → Lambda stores "received" in DynamoDB
SNS notification for segment 2 → Lambda stores "received" in DynamoDB
...
SNS notification for segment N → Lambda stores "received", checks if all NSW segments present
  → If complete: trigger processing Lambda with all segment keys
```

NSW (latitude ~28-37S) maps to segments 7-8 (of 10) in the Himawari full disk. You only need to wait for those 2 segments, not all 10.

DynamoDB schema:
```
PK: "FLDK#B07#20260415#0300"  (product#band#date#time)
SK: "SEG#07"                   (segment number)
Attributes: s3_key, received_at, ttl
```

Conditional write on the last expected segment triggers the processing step.

### Optimization: Don't Wait for All Segments

For fire detection in NSW, you only need segments 7-8 (southern hemisphere mid-latitudes). Start processing as soon as those 2 segments arrive, without waiting for segments covering Japan, the equator, etc.

---

## 5. Polling-Based Ingestion (FIRMS API)

FIRMS doesn't push data -- you must poll. This requires a different pattern.

### Pattern: Scheduled Polling with Change Detection

```
EventBridge (every 5 min) → Lambda (poll FIRMS) → Compare with last result → Emit new detections
```

The Lambda:
1. Calls FIRMS API for NSW bounding box, last 1 day, NRT
2. Compares returned fire points with previously seen points (stored in DynamoDB)
3. New points → fire alert
4. Update DynamoDB with current state

### Deduplication

FIRMS points are identified by `(latitude, longitude, acq_date, acq_time, satellite)`. Use a composite hash of these fields as the DynamoDB key.

---

## 6. Dead Letter Queue (DLQ) Processing

### Pattern: DLQ with Automated Replay

Every processing SQS queue should have a DLQ. Messages that fail 4 times go to the DLQ.

```
Processing Queue (maxReceiveCount=4) → DLQ
                                         ↓
                                    CloudWatch Alarm (DLQ depth > 0)
                                         ↓
                                    Alert + automated analysis
```

DLQ analysis Lambda:
1. Read DLQ messages
2. Log the failure reason (parse the S3 key, check if the file still exists)
3. Common causes: transient S3 errors, malformed NetCDF, OOM on Lambda
4. For transient errors: redrive back to processing queue
5. For persistent errors: log and alert

AWS provides native **DLQ redrive** via the console and API (`StartMessageMoveTask`).

---

## 7. Windowed Aggregation for Temporal Analysis

### Problem

Fire detection improves when comparing the current observation with recent historical background. This requires maintaining a rolling window of recent observations.

### Pattern: Sliding Window State in S3 + DynamoDB

```
New Himawari observation arrives
  → Download current bands (B07, B14, B15)
  → Retrieve last N observations from S3 cache
  → Compute temporal anomaly (current - background)
  → Run fire detection on anomaly
```

Maintain state:
- **DynamoDB**: index of recent observations with S3 keys, observation times
- **S3 cache bucket**: store processed/subsetted bands (NSW region only) for fast retrieval
- **TTL**: expire observations older than 6 hours

### Background Model Update

Keep a running mean and standard deviation of brightness temperatures per pixel, updated with each new observation. Store as a NumPy array in S3:

```python
# On each new observation
background_mean = (1 - alpha) * background_mean + alpha * current_observation
background_std  = (1 - alpha) * background_std  + alpha * abs(current_observation - background_mean)

# Fire detection threshold
anomaly = (current_observation - background_mean) / background_std
fire_mask = anomaly > threshold  # e.g., threshold = 4.0
```

---

## 8. Circuit Breaker for External API Calls

### Pattern: Circuit Breaker for FIRMS API

FIRMS has a 5,000 transaction/10-minute limit. If you exceed it, calls fail. Use a circuit breaker:

```
States: CLOSED (normal) → OPEN (failing) → HALF-OPEN (testing)

CLOSED: normal operation
  → If 3 consecutive failures or rate limit hit → OPEN

OPEN: stop making calls for 2 minutes
  → After timeout → HALF-OPEN

HALF-OPEN: try one call
  → If success → CLOSED
  → If failure → OPEN (reset timeout)
```

Track state in DynamoDB or Lambda environment variables (for short-lived state).

---

## 9. Ordering and Late Data

### NOAA SNS Ordering

SNS does NOT guarantee ordering. File `B07_SEG07` might arrive after `B07_SEG08`. SQS Standard also doesn't guarantee ordering.

Implications:
- Never assume files arrive in order
- Use timestamps from the S3 object key (observation time), not message arrival time
- The scatter-gather pattern (section 4) handles this naturally

### Late-Arriving Data

Occasionally, NOAA data arrives significantly late (minutes to hours after expected). Handle this:

1. Process it anyway -- better a late detection than no detection
2. Mark it as "late" in the alert metadata
3. Don't let late data block current processing

### Out-of-Order Observations

If observation T+20 arrives before T+10:
- Process T+20 immediately with current background
- When T+10 arrives, process it and update background
- Don't emit a "new fire" alert if T+20 already detected it

Track the last processed observation time per pixel region in DynamoDB. Only emit alerts for genuinely new detections.
