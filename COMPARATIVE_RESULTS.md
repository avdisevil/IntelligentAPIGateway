# Comparative Evaluation of an Intelligent API Gateway Against Ten Related Studies

## Abstract

This paper-style results document reports the measurements collected from the
Intelligent API Gateway and compares their scope with the outcomes and metrics
reported in ten related research studies. The gateway was tested in a local
Docker Compose environment in three repeated runs, using 60 requests per
latency scenario and up to 20 concurrent clients. The measured cases included
direct calls to a simulated backend, gateway passthrough, repeated warm-cache
requests, identical-request bursts, and token-bucket rate-limit bursts. Across
the three runs, every 20-request identical GET burst caused one upstream call
and saved 19 calls (95% reduction); all 60 warm-cache requests per run were
cache hits; and the configured initial token-bucket capacity of 15 resulted in
15 accepted and five rejected requests per 20-request burst. In the direct
versus gateway passthrough case, the gateway had a median throughput of 51.46
requests/s against 78.08 requests/s for the direct simulator, with substantially
higher measured latency and one gateway 502 response in 180 requests. These
results are exploratory, host-specific measurements. The cited studies use
different experimental systems, workloads, metrics, and units; consequently,
the document reports a scope-aware comparison rather than claiming a
statistically valid cross-study performance ranking.

**Keywords:** API gateway; Redis; cache; request coalescing; rate limiting;
throughput; latency; comparative evaluation

## 1. Scope of comparison

The evaluation compares measured outcomes from the project with the
experimental measures and reported findings of ten related studies. The
studies concern NoSQL consistency and performance, security architecture
assessment, gateway protocol design, cache invalidation, asynchronous
frameworks, monitoring, geographic service architectures, chaos engineering,
and adaptive API gateways.

This is not a reproduction of those studies. The local gateway benchmark uses
a simulated paid API and measures the complete HTTP request path. It therefore
does not directly reproduce database-operation latency, framework resource
use, architecture-assessment accuracy, or cloud availability as evaluated in
the cited papers.

## 2. Experimental method and metric definitions

### 2.1 Gateway test environment

The gateway and its simulated backend were run with the project's Docker
Compose configuration. The gateway was rebuilt from the current checkout
before the recorded runs. The backend's default simulated processing delay is
50 ms. Three benchmark runs were completed; each run used 60 requests for the
direct, passthrough, and warm-cache latency scenarios, with maximum client
concurrency set to 20. The coalescing and rate-limit tests each used a burst of
20 concurrent requests.

The recorded environment was a Windows workstation with Docker Desktop. Exact
CPU model, memory capacity, container resource limits, CPU utilization, and
memory utilization were not recorded. No separate warm-up phase, randomized
scenario order, or confidence-interval analysis was used.

### 2.2 Gateway scenarios

1. **Direct backend:** HTTP POST requests sent directly to the simulator.
2. **Gateway passthrough:** HTTP POST requests sent to the gateway and
   forwarded to the simulator with API-key authentication and gateway
   middleware enabled.
3. **Warm cache:** one unique GET request to populate the cache, followed by
   60 sequential repetitions of that URL. The response `X-Cache` header was
   recorded.
4. **Identical-request coalescing:** 20 concurrent GET requests to a new,
   identical URL, with Prometheus counter values recorded before and after the
   burst. Cache-hit and cache-miss deltas were checked to distinguish
   coalescing from cache reuse.
5. **Rate-limit burst:** 20 concurrent POST requests using the configured
   rate-limit test key, whose initial token-bucket capacity is 15. HTTP 200
   and HTTP 429 responses were counted.

### 2.3 Metric definitions

- **Throughput:** number of client requests divided by elapsed wall-clock
  seconds for the scenario.
- **Latency:** client-observed end-to-end HTTP time, in milliseconds,
  measured with a monotonic timer. Reported percentiles use nearest-rank
  selection.
- **HTTP outcome:** number of requests receiving each HTTP status code.
- **Warm-cache hit ratio:** number of warm requests with `X-Cache: HIT`
  divided by the number of warm requests.
- **Coalescing reduction:** saved duplicate requests divided by total
  identical requests in the burst. The upstream-call and coalescing-counter
  deltas were used for verification.
- **Rate-limit burst match:** observed accepted requests compared with the
  configured initial token-bucket capacity. This is a result for the tested
  burst, not a general accuracy measure.
- **Simulated cost:** simulator call count multiplied by its fixed simulated
  price of USD 0.50 per call. This is illustrative test accounting, not an
  actual commercial API price.

For each project scenario, the aggregate is the median of the three run-level
measurements, except where counts were identical in every run. Ranges are
shown to expose run-to-run variation.

## 3. Gateway results

### 3.1 Direct backend and gateway passthrough

**Table 1.** End-to-end POST results at a maximum client concurrency of 20.
Latency is in milliseconds; throughput is in requests per second.

| Measure | Direct backend, median (range) | Gateway passthrough, median (range) |
|---|---:|---:|
| Requests per run | 60 | 60 |
| Throughput (requests/s) | 78.08 (35.37–120.88) | 51.46 (21.05–64.09) |
| Mean latency (ms) | 113.01 (99.03–323.37) | 353.70 (287.68–868.89) |
| p50 latency (ms) | 87.07 (81.63–298.50) | 348.09 (290.38–924.74) |
| p95 latency (ms) | 260.75 (235.37–883.39) | 449.30 (370.00–1,384.42) |
| p99 latency (ms) | 500.62 (330.74–1,161.94) | 464.11 (371.08–1,430.13) |
| HTTP 200 responses | 180/180 | 179/180 |
| HTTP 502 responses | 0/180 | 1/180 |

Using the medians of the three run-level measurements, gateway passthrough
throughput was **34.09% lower** than direct simulator throughput. Gateway
passthrough p50 latency was **299.78% higher** and p95 latency was **72.31%
higher**. The p99 median was lower in the gateway series than in the direct
series because the run-level distributions were highly variable; this does not
establish that the gateway improves tail latency. One gateway request returned
HTTP 502, and the underlying downstream error was not determined.

The measured throughput and latency spread is large. These figures should be
treated as exploratory results for the tested local stack, not stable capacity
estimates.

### 3.2 Response cache

**Table 2.** Cold and warm cache results.

| Run | Cold request status / header | Cold latency (ms) | Warm requests | Warm cache hits | Warm p50 (ms) | Warm p95 (ms) | Warm p99 (ms) |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | 200 / `MISS` | 169.75 | 60 | 60 (100%) | 16.13 | 36.65 | 80.34 |
| 2 | 200 / `MISS` | 170.78 | 60 | 60 (100%) | 8.68 | 27.23 | 33.69 |
| 3 | 200 / `MISS` | 172.95 | 60 | 60 (100%) | 11.44 | 31.64 | 36.64 |
| **Median warm result** | — | — | **60** | **60 (100%)** | **11.44** | **31.64** | **36.64** |

The observed warm-cache hit ratio was 100% in all three trials. The cold
request is a single observation per run, while warm latency summarizes 60
requests; this is not a paired latency experiment and should not be used to
claim a statistically established cache speedup.

### 3.3 Request coalescing

**Table 3.** Identical concurrent GET burst results.

| Run | Incoming requests | Upstream calls | Saved duplicate calls | Cache misses | Cache hits | Upstream reduction | Burst p50 (ms) | Burst p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 1 | 19 | 20 | 0 | 95% | 216.15 | 237.14 |
| 2 | 20 | 1 | 19 | 20 | 0 | 95% | 268.65 | 278.42 |
| 3 | 20 | 1 | 19 | 20 | 0 | 95% | 280.55 | 307.23 |

For this specific same-process burst, all 20 requests missed the response
cache, while the coalescer recorded 19 saved calls and the upstream-call
counter increased by one. This supports attributing the 95% reduction in
duplicate upstream calls to request coalescing rather than cache hits.

The simulator charges USD 0.50 per call. Under that fixed test assumption,
the burst's simulated cost was USD 0.50 with coalescing versus USD 10.00 for
20 independent calls, a simulated saving of USD 9.50 per burst. This cost
result is illustrative and depends entirely on the simulator's artificial
pricing rule.

### 3.4 Rate-limit burst

**Table 4.** Concurrent requests against an initially configured token bucket
with capacity 15.

| Run | Requests | HTTP 200 accepted | HTTP 429 denied | Other statuses | Match to initial capacity |
|---|---:|---:|---:|---:|---|
| 1 | 20 | 15 | 5 | 0 | Yes |
| 2 | 20 | 15 | 5 | 0 | Yes |
| 3 | 20 | 15 | 5 | 0 | Yes |

The observed accepted count matched the configured initial capacity in all
three bursts. The experiment did not measure long-duration refill accuracy,
policy behavior across many API keys, or the dynamic analyzer's adaptation
over time. Therefore, the result is evidence for one configured burst case,
not a general rate-limiter accuracy percentage.

## 4. Outcomes and measures reported in the related studies

The following table summarizes the metrics and findings available in the
reviewed sources and supplied paper summaries. **NR** means that a numerical
value was not reported in the accessible abstract or summary used for this
comparison. Qualitative results are identified as such; they are not treated
as numerical measurements.

**Table 5.** Literature outcomes and measured metric families.

| Ref. | Study domain and design | Metrics measured in the study | Reported outcome available for this comparison |
|---|---|---|---|
| [1] | Cloud NoSQL consistency; MongoDB, Cassandra, and Redis under single-region and multi-region workloads with different consistency settings. | Throughput, response time, error rate, CPU, and RAM. | The supplied review reports Redis single-region write throughput of approximately **4,000 requests/s** in its best case and write latency near **2 ms** in evaluated cases. These figures are study-specific and were not independently confirmed against the full paper in this comparison. |
| [2] | Controlled assessment using security-annotated microservice architecture decomposition models; 60 students and 10 industry experts assessed two reference systems. | Security metric values, expert agreement, task performance, and ordinal-regression correlation with expert assessment. | The reported outcome is qualitative here: annotated models improved assessment correctness, especially for less-experienced participants. No comparable gateway security-assessment score was measured. |
| [3] | Load comparison of API design techniques for API gateways implemented as .NET prototypes; the study concerns REST, gRPC, and Apache Thrift. | Response time, throughput, and availability under load. | The supplied summary says protocol choice affected gateway performance and availability. Numerical results were unavailable for verification in this comparison; no numeric cross-study ranking is reported. |
| [4] | Declarative cache invalidation that separates microservice business logic from cache-update rules; considers Redis and Memcached. | Cache consistency, performance implications, inter-service dependence, and cache-management effectiveness. | The supplied summary describes reduced coupling and cache-management support as intended/reported outcomes. No numeric comparative result was available in the reviewed summary. |
| [5] | Flask microservices comparison of MongoDB document storage and Redis key-value storage using CRUD and aggregation over nested transport data. | Operation latency, throughput, and comparative CRUD/aggregation performance. | The accessible summary reports average read latency of **0.37 ms for Redis vs 0.93 ms for MongoDB**, and read-by-ID latency of **1.05 ms vs 8.73 ms**, respectively. These are database-operation measurements, not end-to-end HTTP gateway latency. |
| [6] | Reactive versus imperative Spring applications with query and resource workloads, including an API Gateway context. | Query processing time, CPU, RAM, and latency with a gateway. | The reported qualitative outcome is workload-dependent: reactive I/O was faster and used less RAM; imperative sequential transactional work was faster; reactive processing showed lower latency in the gateway context. Numerical values were not available in the supplied comparison summary. |
| [7] | Monitoring microservices and predictive models; compares Spring Boot and Quarkus implementations. | CPU, memory, uptime, and performance statistics. | The supplied summary reports up to **80% lower memory use** and **95% lower CPU use** for Quarkus. The cited abstract's uptime wording (“decreased by 119%”) is ambiguous and is not interpreted here. |
| [8] | Service-oriented geographic-data sharing and computing framework, validated with a runoff-simulation case. | System effectiveness, data-access efficiency, and application-level performance. | A qualitative case-study outcome reports use of Redis caching to avoid repeated network data retrieval. No numerical gateway-comparable latency or throughput value was available in the supplied summary. |
| [9] | Exploratory chaos-engineering experiment on serverless and containerized cloud-native applications under varying user loads and injected delays. | Latency, throughput, availability, error behavior, and recovery/dependability indicators. | The study reports that injected delays increased latency and exposed availability issues at some stress levels. Numerical values were not available in the supplied comparison summary. |
| [10] | Proposed AI-powered gateway combining anomaly detection, request profiles, and reinforcement-learning-oriented policy changes. | Anomaly-detection effectiveness, adaptive-policy response, and API-security performance. | The accessible publisher summary asserts improvements over traditional methods but supplies no reproducible quantitative baseline or numeric outcome in the material reviewed. No numerical advantage is attributed to the paper or this gateway. |

## 5. Scope-aware comparison

**Table 6.** What the gateway results do and do not establish relative to the
literature.

| Literature area | Comparable project result | Comparison outcome |
|---|---|---|
| NoSQL performance and consistency [1], [5] | Warm-cache HTTP p50 11.44 ms; gateway passthrough p50 348.09 ms; local simulator measurements. | These are full HTTP-path measurements, not Redis/MongoDB operation benchmarks. The data do not establish that the gateway or its Redis layer is faster than the database studies. |
| Security tactics and assessment [2] | Rate-limit burst accepted 15/20 and denied 5/20 for a configured capacity of 15. | This measures request admission behavior only; it is not a security metric, attack-detection rate, expert agreement score, or architecture-assessment result. |
| Gateway protocol performance [3] | Direct simulator and gateway passthrough end-to-end latency and throughput. | No competing API protocols were tested. One local REST-like path cannot be ranked against the paper's protocol variants. |
| Cache management and invalidation [4] | 60/60 repeated warm requests were cache hits; identical fresh GET bursts reduced upstream calls by 95%. | Cache reuse and duplicate suppression were measured. Invalidation correctness, stale-data consistency, and business-rule coupling were not measured. |
| Reactive/imperative performance [6] | Gateway end-to-end HTTP latency and throughput. | CPU and RAM were not measured, and no Spring implementation was benchmarked. No framework or resource-use advantage is established. |
| Monitoring performance [7] | Application-level counters and latency metrics were observed during tests. | CPU, memory, and uptime were not sampled. The project cannot be compared quantitatively with Spring Boot/Quarkus monitoring results. |
| Geographic service-oriented computing [8] | No geographic workload was included. | No numerical comparison is available. |
| Chaos engineering [9] | Normal-operation passthrough, cache, coalescing, and rate-limit tests. | Fault injection, recovery, and availability under induced failures were not measured. |
| AI/adaptive gateway [10] | One initial token-bucket burst matched its configured capacity in three runs. | The project did not evaluate threat detection, machine learning, reinforcement learning, or long-term adaptation; no performance superiority is established. |

The only direct measured advantages demonstrated within this gateway's own
test environment are **cache reuse for repeated requests** and **reduced
duplicate upstream calls for identical concurrent GETs**. These outcomes are
not numeric wins over the ten papers because the studies do not provide a
shared testbed, workload, or common endpoint measurement. The gateway
passthrough test, in contrast, measured lower throughput and higher p50/p95
latency than the direct local simulator baseline in the observed runs.

## 6. Limitations

1. **Cross-study incompatibility:** The papers measure different systems and
   units, including database-operation time, application latency, security
   assessment, CPU/RAM, availability, and application-level outcomes. A direct
   numerical ranking would be invalid without reproducing compatible
   experiments.
2. **Local test environment:** Results are from a single Windows workstation
   and local Docker Compose deployment; hardware details and resource limits
   were not recorded.
3. **Observed variability:** Direct and gateway throughput and latency varied
   considerably among the three runs. No warm-up period, randomized trial
   ordering, confidence intervals, or significance tests were used.
4. **One failed request:** One of 180 gateway passthrough requests returned
   HTTP 502. The cause was not determined.
5. **Limited rate-limit scope:** The rate-limit result covers a 20-request
   burst against an initial bucket capacity of 15; it is not a sustained-load
   or adaptive-policy evaluation.
6. **Simulated backend and cost:** A fixed 50 ms default delay and USD 0.50
   per-call simulator price do not represent a production provider.
7. **Literature access:** Some paper summaries were based on accessible
   abstracts or the supplied review rather than full-text reanalysis. Where
   numeric details were unavailable or uncertain, they are identified as
   such rather than estimated.
8. **Unmeasured resource and resilience outcomes:** CPU, RAM, availability
   under faults, recovery time, stale-data correctness, and performance across
   multiple gateway replicas were not measured.

## 7. Conclusion

Across three local trials, the gateway served all 60 repeated warm-cache
requests as hits, reduced upstream calls from 20 to one in each identical GET
burst, and admitted exactly 15 of 20 requests in the tested initial
rate-limit bursts. These are measurable functional outcomes for cache,
coalescing, and token-bucket enforcement. The measured passthrough tests did
not show an overall latency or throughput advantage over direct simulator
calls; their results were variable and included one HTTP 502.

The related papers provide context through their own metrics and findings,
including NoSQL throughput/latency, security-assessment performance,
gateway-protocol response time and availability, cache consistency,
framework resource use, monitoring performance, and fault response. Because
the workloads and measurement units differ, this comparison supports a
descriptive positioning of the gateway's measured outcomes, not a claim that
the gateway outperforms those studies.

## References

[1] “Impacts of data consistency levels in cloud-based NoSQL for data-intensive
applications.” *Journal of Cloud Computing* (2024).
[https://doi.org/10.1186/s13677-024-00716-7](https://doi.org/10.1186/s13677-024-00716-7).

[2] “Understanding security tactics in microservice APIs using annotated
software architecture decomposition models – a controlled experiment.”
*Empirical Software Engineering* (2025).
[https://doi.org/10.1007/s10664-024-10601-1](https://doi.org/10.1007/s10664-024-10601-1).

[3] “Performance and Availability Analysis of API Design Techniques for API
Gateways.” *Arabian Journal for Science and Engineering*, published online
2024; volume 50, issue 15.
[https://doi.org/10.1007/s13369-024-09474-9](https://doi.org/10.1007/s13369-024-09474-9).

[4] “Cache invalidation based on a declarative approach for separating
business logic of microservices from cache update rules.”
*Eastern-European Journal of Enterprise Technologies* (2025).
[https://doi.org/10.15587/1729-4061.2025.325932](https://doi.org/10.15587/1729-4061.2025.325932).

[5] “Performance Analysis of NoSQL Databases: MongoDB Document Store and Redis
Key-Value Store in Microservices-Based Applications Using Flask.”
*International Journal Software Engineering and Computer Science* (2025).
[https://doi.org/10.35870/ijsecs.v5i2.4206](https://doi.org/10.35870/ijsecs.v5i2.4206).

[6] “Examination of the performance and scalability of a web application in a
reactive and imperative approach using the Spring Framework.” *Journal of
Computer Sciences Institute* 32 (2024), 210–216.
[https://doi.org/10.35784/jcsi.6291](https://doi.org/10.35784/jcsi.6291).

[7] “Enhancing Monitoring Performance: A Microservices Approach to Monitoring
with Spyware Techniques and Prediction Models.” *Sensors* 24(13), 4212
(2024).
[https://doi.org/10.3390/s24134212](https://doi.org/10.3390/s24134212).

[8] “Research on Service-Oriented Sharing and Computing Framework of
Geographic Data for Geographic Modeling and Simulation.” *Applied Sciences*
14(24), 11983 (2024).
[https://doi.org/10.3390/app142411983](https://doi.org/10.3390/app142411983).

[9] “Exploring the impact of chaos engineering with various user loads on
cloud native applications: an exploratory empirical study.” *Computing*
106(7), 2389–2425 (2024).
[https://doi.org/10.1007/s00607-024-01292-z](https://doi.org/10.1007/s00607-024-01292-z).

[10] “AI-Powered API Gateways for Adaptive Rate Limiting and Threat
Detection.” *International Journal of Artificial Intelligence, Data Science,
and Machine Learning*.
[https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112](https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112).
