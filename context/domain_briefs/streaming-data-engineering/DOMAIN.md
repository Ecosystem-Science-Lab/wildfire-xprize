# Streaming Data Engineering for Wildfire Detection

## Scope and Relevance to XPRIZE (NSW, Australia -- April 2026)

This domain brief covers the real-time data ingestion, processing, and dissemination infrastructure needed to achieve sub-10-second processing latency once satellite data arrives. The system must ingest data from multiple satellite sources (Himawari-9, VIIRS, Sentinel-3, FIRMS) and route it through fire detection algorithms with minimal delay.

### Key Constraints

- **Data arrives in us-east-1** (all NOAA NODD data is in AWS us-east-1)
- **Competition is in NSW, Australia** -- results must be delivered with low latency to the ground truth team
- **Multiple cadences**: Himawari every 10 min, VIIRS 2--4x/day, Sentinel-3 ~1x/day
- **Sub-10-second processing target** means the pipeline budget is tight once data lands in S3
- **NetCDF/HSD files** range from ~1 MB (single-band segment) to ~100 MB (full-disk multi-band)

---

## System Architecture Overview

### Event-Driven Ingestion Pipeline

The core pattern is: **NOAA SNS -> Your SQS Queue -> Processing (Lambda or ECS) -> Detection Algorithm -> Alert**

```
┌─────────────────────────────────────────────────────────────┐
│                    NOAA NODD (us-east-1)                    │
│                                                             │
│  S3: noaa-himawari9   SNS: NewHimawariNineObject           │
│  S3: noaa-nesdis-n20  SNS: NewNOAA20Object                 │
│  S3: noaa-goes19      SNS: NewGOES19Object                 │
└──────────────┬──────────────────────────────────────────────┘
               │ SNS notification on every new S3 object
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    YOUR AWS ACCOUNT (us-east-1)              │
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐  │
│  │ SQS      │───▶│ Filter/Route │───▶│ Processing Tier   │  │
│  │ Queues   │    │ (Lambda)     │    │ (ECS Fargate or   │  │
│  │          │    │              │    │  Lambda)           │  │
│  └──────────┘    └──────────────┘    └───────┬───────────┘  │
│                                              │              │
│                                              ▼              │
│                                     ┌────────────────────┐  │
│                                     │ Fire Detection     │  │
│                                     │ Algorithm          │  │
│                                     └────────┬───────────┘  │
│                                              │              │
│                                              ▼              │
│                                     ┌────────────────────┐  │
│                                     │ Alert/Results      │  │
│                                     │ (SNS/API/WS)       │  │
│                                     └────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Why SQS Between SNS and Processing

1. **Buffering**: SQS absorbs bursts. NOAA pushes thousands of files/day; not all are relevant.
2. **Retry semantics**: If Lambda/ECS fails, SQS retries. Direct SNS->Lambda has limited retry.
3. **Filtering**: Process SQS messages in a lightweight Lambda that filters by product type, band, region -- only forward relevant files to expensive processing.
4. **Backpressure**: SQS queue depth is a natural backpressure signal. You can monitor it and scale processing accordingly.
5. **Dead letter queues**: Failed messages go to DLQ for debugging, not lost.

### Processing Tier Choices

| Option | Cold Start | Max Duration | Memory | Best For |
|--------|-----------|-------------|--------|----------|
| Lambda | 100--500ms (Python) | 15 min | 10 GB | Filtering, small file processing |
| Lambda + SnapStart | ~200ms | 15 min | 10 GB | Java/.NET only |
| ECS Fargate | 30--60 sec task start | Unlimited | 120 GB | Heavy processing (NetCDF, ML inference) |
| ECS on EC2 | 0 (always-on) | Unlimited | Instance memory | Lowest latency, highest cost |
| Lambda + Provisioned Concurrency | ~0ms | 15 min | 10 GB | Pre-warmed, ~$15/mo per slot |

For sub-10-second processing: **Lambda with provisioned concurrency** for the filter/dispatch layer, and **ECS Fargate tasks pre-warmed** (or always-running ECS services on EC2) for the heavy NetCDF processing and ML inference.

---

## Data Flow: Himawari-9 Full Disk Ingestion

This is the most time-critical path since Himawari provides continuous 10-minute monitoring of NSW.

### Timeline for a Single Observation

```
T+0:00        Himawari-9 AHI scans Earth (10-min full disk scan)
T+0:10        Scan complete, downlinked to JMA ground station
T+~1:00       JMA processes raw data to L1b HSD format
T+~2:00       JMA transmits to NOAA via dedicated link
T+~2:30       NOAA writes to S3 (noaa-himawari9)
T+~2:31       SNS notification fires (NewHimawariNineObject)
T+~2:31       Your SQS receives message
T+~2:32       Filter Lambda triggers, identifies fire-relevant bands
T+~2:33       Processing Lambda/ECS reads NetCDF from S3
T+~2:38       Fire detection algorithm runs (5 sec budget)
T+~2:40       Alert generated
```

Total: **~2.5 minutes from observation to alert**, dominated by upstream ground processing and data relay. Your processing adds ~10 seconds.

### What You Control vs What You Don't

| Phase | Latency | Your control? |
|-------|---------|--------------|
| Satellite scan to ground station | ~10 sec | No |
| Ground processing (JMA) | ~1 min | No |
| JMA -> NOAA relay | ~30--60 sec | No |
| NOAA -> S3 | 0.2--0.3 sec | No |
| SNS -> SQS -> Your processing | **~10 sec** | **Yes** |

---

## Key Infrastructure Components

### SQS Queue Configuration

For satellite data ingestion, configure SQS queues as:

- **Visibility timeout**: 60 seconds (enough for processing, short enough for fast retry)
- **Message retention**: 4 days (default, catch up after outages)
- **Receive wait time**: 20 seconds (long polling -- reduces empty receives by ~90%)
- **Max receive count**: 4 (before DLQ)
- **DLQ**: Separate queue for failed messages

Use **separate queues per data source** (one for Himawari, one for VIIRS, one for GOES) to isolate failures and tune independently.

### Lambda Event Source Mapping

For SQS -> Lambda with minimum latency:

- **Batch size**: 1--5 for latency-sensitive paths (trade throughput for latency)
- **Maximum batching window**: 0 seconds (no waiting)
- **Provisioned mode** (if available): MinimumPollers=5, MaximumPollers=50

For throughput-oriented paths (bulk VIIRS reprocessing):

- **Batch size**: 10
- **Maximum batching window**: 5 seconds
- **Report batch item failures**: enabled

### S3 Access Pattern

All NOAA buckets are public and in us-east-1. To minimize download latency:

1. **Run processing in us-east-1** -- same-region S3 reads are <10ms first-byte latency
2. **Use `--no-sign-request`** (CLI) or unsigned client (SDK) -- skipping SigV4 saves ~5ms
3. **Pre-warm connections** -- keep S3 client alive between invocations (Lambda container reuse)
4. **Download only needed bands** -- for Himawari, each band is a separate file; only download B07, B14, B15 for fire detection

---

## Multi-Source Fusion Architecture

The system must handle different cadences and merge detections:

```
Himawari-9 (every 10 min, 2km)  ──┐
                                   ├──▶ Fusion Engine ──▶ Unified Alert
VIIRS (2-4x/day, 375m)           ──┤     (DynamoDB +      Stream
                                   │      event-driven)
FIRMS API (3hr NRT)              ──┤
                                   │
Sentinel-3 SLSTR (1x/day, 1km)  ──┘
```

### Temporal Alignment

Each source arrives at different times with different latencies. The fusion engine needs:

- **Event time** (when the satellite observed) not **arrival time** (when data hit S3)
- **Deduplication** -- the same fire may be detected by Himawari, then VIIRS, then FIRMS
- **Confidence upgrade** -- initial Himawari detection at 2km, upgraded when VIIRS confirms at 375m

Use DynamoDB with **fire event ID** as partition key and **observation time** as sort key. TTL for auto-expiration of stale events.

---

## Monitoring and Alerting

### Key Metrics to Track

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| SQS `ApproximateAgeOfOldestMessage` | CloudWatch | >60 sec |
| SQS `ApproximateNumberOfMessagesVisible` | CloudWatch | >100 |
| Lambda duration (P99) | CloudWatch | >10 sec |
| Lambda errors | CloudWatch | >0 in 5 min window |
| S3 download latency | Custom metric | >2 sec |
| End-to-end detection latency | Custom metric | >30 sec |
| DLQ message count | CloudWatch | >0 |
| FIRMS API response time | Custom metric | >5 sec |

### Data Gap Detection

NOAA SNS notifications stop when upstream data stops. Detect gaps by:

- Track last-received timestamp per source per product
- Alert if no Himawari FLDK data for >15 minutes (expected every 10 min)
- Alert if no VIIRS data for >6 hours at expected overpass times

---

## Cost Model (Approximate)

For continuous operation during a multi-week competition:

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| SQS (3 queues, ~100K msgs/day each) | ~$10 | Negligible |
| Lambda (filter, ~100K invocations/day) | ~$5 | 128MB, <1 sec each |
| Lambda (processing, ~1K invocations/day) | ~$20 | 2GB, ~5 sec each |
| ECS Fargate (always-on processor) | ~$100 | 2 vCPU, 8GB, 1 task |
| S3 data transfer (same region) | $0 | All data in us-east-1 |
| DynamoDB (fusion state) | ~$10 | On-demand mode |
| CloudWatch | ~$10 | Metrics + alarms |
| **Total** | **~$155/mo** | Excluding ML inference compute |

If ML inference requires GPU: add ~$300--700/mo for a `g4dn.xlarge` or equivalent spot instance.
