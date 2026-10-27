# One-to-One Comparison Study: Intelligent API Gateway and Ten Related Research Papers

## Abstract

This study compares the measured outcomes of the Intelligent API Gateway with
the metrics and results reported for ten related papers. The gateway was
evaluated in three local Docker Compose runs using a simulated backend: direct
backend requests, gateway passthrough, warm-cache requests, identical
concurrent GET requests, and a token-bucket rate-limit burst. The clearest
measured gateway outcomes were 60/60 warm cache hits per run, 19 of 20
duplicate upstream requests suppressed per identical-request burst, and 15
accepted versus five denied requests in a 20-request burst against a bucket
capacity of 15. In the direct versus gateway passthrough scenario, the gateway
median was 51.46 requests/s compared with 78.08 requests/s for direct backend
requests; median p50 latency was 348.09 ms compared with 87.07 ms. The papers
cover different systems and workloads, so a numerical win over them cannot be
claimed from these measurements. The comparison below matches metrics where
possible and explicitly identifies non-comparable or unmeasured outcomes.

## 1. Comparison method

### 1.1 Gateway test configuration

- Environment: local Docker Compose deployment on a Windows workstation;
  gateway image rebuilt from the current checkout.
- Backend: project simulator with a configured default processing delay of
  50 ms and a simulated charge of USD 0.50 per backend call.
- Repetitions: three runs.
- Direct backend and gateway passthrough scenarios: 60 POST requests per run,
  maximum client concurrency 20.
- Warm cache scenario: one cold GET followed by 60 sequential repetitions of
  the same URL per run.
- Coalescing scenario: 20 concurrent requests for the same fresh GET URL per
  run.
- Rate-limit scenario: 20 concurrent requests per run, using an API key with
  initial token bucket capacity 15.

### 1.2 Metric definitions and aggregation

- **Throughput:** client requests divided by scenario elapsed time.
- **Latency:** end-to-end client-observed HTTP duration; p50, p95, and p99
  percentiles were calculated for each run.
- **Cache hit rate:** warm requests returning `X-Cache: HIT` divided by warm
  requests.
- **Coalescing reduction:** saved duplicate requests divided by the 20
  requests in the burst. Upstream-call, cache-miss, cache-hit, and
  coalescing-counter deltas were checked.
- **Rate-limit outcome:** HTTP 200 accepted requests and HTTP 429 denied
  requests in the burst.
- **Error rate:** non-200 responses divided by all requests in the
  direct-versus-gateway passthrough scenarios.
- **Three-run summary:** median of the three run-level values; the observed
  range is also shown.

Hardware model, container resource limits, CPU and RAM utilization, warm-up
phase, confidence intervals, and significance tests were not recorded. Paper
results are reproduced from the supplied literature review and accessible
abstracts; exact values not available there are marked “not reported here.”

## 2. Gateway measurements used in the comparison

**Table 1.** Summary of gateway test results. Latencies are milliseconds.

| Gateway scenario | Main measured result | Run-to-run range / detail |
|---|---|---|
| Direct simulator POST, concurrency 20 | 78.08 requests/s; p50 87.07; p95 260.75; p99 500.62 | Throughput 35.37–120.88 requests/s; p50 81.63–298.50; p95 235.37–883.39; 180/180 responses were HTTP 200. |
| Gateway POST passthrough, concurrency 20 | 51.46 requests/s; p50 348.09; p95 449.30; p99 464.11 | Throughput 21.05–64.09 requests/s; p50 290.38–924.74; p95 370.00–1,384.42; 179/180 responses HTTP 200 and one HTTP 502. |
| Warm response cache | 60/60 requests were cache hits in each run (100%); median p50 11.44; p95 31.64; p99 36.64 | Warm-cache throughput median 71.04 requests/s; range 50.08–84.51. Cold request per run returned HTTP 200 with `X-Cache: MISS`. |
| Identical concurrent GET burst | 1 upstream call from 20 requests; 19 saved (95% reduction) in every run | 20 cache misses and zero cache hits per run, confirming reduction from coalescing and not cache hits. Burst p50 216.15–280.55; p95 237.14–307.23. |
| Simulated cost for identical GET burst | USD 0.50 observed vs USD 10.00 for 20 separate simulator calls; USD 9.50 simulated saving | Assumes simulator's fixed USD 0.50 charge per call; not a real provider price. |
| Token-bucket rate-limit burst | 15 HTTP 200 accepted and 5 HTTP 429 denied from 20 requests in each run | Matched the configured initial bucket capacity of 15 in all three trials. |

Across the direct and gateway POST trials, the gateway had 34.09% lower median
throughput, 299.78% higher median p50 latency, and 72.31% higher median p95
latency than the direct simulator. This is the result of the local test and
should not be presented as a universal property of the gateway. One of 180
gateway POST requests returned HTTP 502; the cause was not determined.

## 3. One-to-one comparison with the ten papers

**Table 2.** Side-by-side comparison of each paper's relevant metric or
reported outcome with the nearest gateway measurement. “Not measured” means
the gateway experiment did not collect that metric. “Not directly comparable”
means the named metrics exist on both sides but measure different workloads,
systems, or layers.

| # / paper | Paper's metrics and reported outcome | Corresponding gateway metric/result | One-to-one interpretation |
|---|---|---|---|
| **1. Impacts of data consistency levels in cloud-based NoSQL for data-intensive applications**. *Journal of Cloud Computing* (2024). [DOI](https://doi.org/10.1186/s13677-024-00716-7) | Cloud and multi-region MongoDB, Cassandra, and Redis experiments. Measures throughput, response time, error rate, CPU, and RAM. The supplied review reports Redis best-case single-region write throughput of about **4,000 requests/s** and write response times near **2 ms**. | Direct simulator: **78.08 requests/s**, p50 **87.07 ms**. Gateway passthrough: **51.46 requests/s**, p50 **348.09 ms**. Warm cached HTTP responses: p50 **11.44 ms**, 60/60 hits. Gateway error rate: **1/180 (0.56%)**; direct simulator: 0/180. CPU/RAM not measured. | **Throughput and latency are not directly comparable:** paper numbers describe database operations under cloud consistency settings; gateway numbers describe end-to-end HTTP calls and middleware. The measured gateway did not outperform the direct simulator. The paper's cited approximate values require confirmation from its full text before formal quotation. |
| **2. Understanding security tactics in microservice APIs using annotated software architecture decomposition models – a controlled experiment**. *Empirical Software Engineering* (2025). [DOI](https://doi.org/10.1007/s10664-024-10601-1) | Security metric values, expert agreement, task performance, and relationship between model metrics and expert assessment; experiment included 60 students and 10 industry experts. Annotated models reportedly helped assessment correctness. | One operational traffic-control result: **15/20 accepted and 5/20 denied** in each rate-limit burst, matching the configured initial token capacity. No security architecture metric, expert evaluation, attack-detection rate, or security task study. | **Not directly comparable.** The paper measures architecture-security assessment; the gateway test measures request admission. The result shows runtime enforcement behavior, not a better security assessment or stronger security outcome. |
| **3. Performance and Availability Analysis of API Design Techniques for API Gateways**. *Arabian Journal for Science and Engineering* (online 2024; issue metadata later). [DOI](https://doi.org/10.1007/s13369-024-09474-9) | Compares REST, gRPC, and Apache Thrift gateway prototypes. Measures response time, throughput, and availability under load. Detailed numerical findings were not accessible for this comparison. | Local HTTP gateway passthrough: **51.46 requests/s**, p50 **348.09 ms**, p95 **449.30 ms**; one HTTP 502 among 180 requests. Direct simulator: **78.08 requests/s**, p50 **87.07 ms**, p95 **260.75 ms**; no failed requests among 180. No competing protocols tested. | **Partial metric overlap, no protocol comparison.** Latency and throughput were measured, but this gateway uses only its current HTTP interface and simulator. The one HTTP 502 is not a controlled availability study. No superiority over REST/gRPC/Thrift can be inferred. |
| **4. Cache invalidation based on a declarative approach for separating business logic of microservices from cache update rules**. *Eastern-European Journal of Enterprise Technologies* (2025). [DOI](https://doi.org/10.15587/1729-4061.2025.325932) | Declarative cache update/invalidation rules, cache consistency, performance implications, inter-service dependence, and cache-management effectiveness. The accessible summary describes separation of cache rules from business logic; no comparable numeric result was available. | Warm cache: **60/60 hits (100%)** in every run; p50 **11.44 ms**, p95 **31.64 ms**. Coalescing: **19/20 duplicate upstream calls suppressed**. No stale-data correctness or invalidation test. | **Comparable only for cache use/performance at a high level.** The gateway demonstrates repeated response reuse and miss-burst deduplication. It does not implement or test the paper's declarative invalidation rules, cache consistency guarantees, or coupling reduction. |
| **5. Performance Analysis of NoSQL Databases: MongoDB Document Store and Redis Key-Value Store in Microservices-Based Applications Using Flask**. *International Journal Software Engineering and Computer Science* (2025). [DOI](https://doi.org/10.35870/ijsecs.v5i2.4206) | CRUD and aggregation latency/throughput in Flask microservices. The supplied accessible summary reports average read latency **0.37 ms Redis vs 0.93 ms MongoDB**, and read-by-ID latency **1.05 ms Redis vs 8.73 ms MongoDB**. | Warm HTTP cache response p50 **11.44 ms**, p95 **31.64 ms**. Gateway POST passthrough p50 **348.09 ms**. Redis command-level latency was not separately measured. | **Not directly comparable.** Paper values are database-operation latency; gateway values include HTTP, middleware, serialization, and client/network overhead. Do not conclude the gateway is faster or slower than Redis/MongoDB based on these values. |
| **6. Examination of the performance and scalability of a web application in a reactive and imperative approach using the Spring Framework**. *Journal of Computer Sciences Institute* 32 (2024), 210–216. [DOI](https://doi.org/10.35784/jcsi.6291) | Compares reactive and imperative Spring applications. Measures query processing time, CPU, RAM, and latency with an API Gateway. Reported outcomes vary by workload: reactive I/O and gateway-context latency favored reactive; imperative sequential transactional work was faster. | Gateway end-to-end latency: passthrough p50 **348.09 ms**, p95 **449.30 ms**; warm cache p50 **11.44 ms**. CPU/RAM and equivalent Spring variants not measured. | **Latency is only loosely comparable.** Workloads and frameworks differ, and the project did not test a Spring gateway or resource usage. No reactive-framework or CPU/RAM advantage is established. |
| **7. Enhancing Monitoring Performance: A Microservices Approach to Monitoring with Spyware Techniques and Prediction Models**. *Sensors* 24(13), 4212 (2024). [DOI](https://doi.org/10.3390/s24134212) | Measures CPU, memory, uptime, and performance in Spring Boot and Quarkus monitoring systems. Supplied review reports up to **80% lower memory** and **95% lower CPU** for Quarkus. The abstract's “uptime decreased by 119%” wording is ambiguous. | The gateway's Prometheus request, cache, upstream, and rate-limit counters were used to evaluate behaviors. CPU, memory, uptime, and monitoring overhead were not sampled. | **Not directly comparable.** The gateway reports request-level operational outcomes, not comparative monitoring-framework resource consumption. No claim of lower CPU/RAM or better uptime is supported. |
| **8. Research on Service-Oriented Sharing and Computing Framework of Geographic Data for Geographic Modeling and Simulation**. *Applied Sciences* 14(24), 11983 (2024). [DOI](https://doi.org/10.3390/app142411983) | Geographic-data service framework validated with a runoff-simulation case. Measures system effectiveness, data access efficiency, and application performance; uses Redis caching to avoid repeated network retrieval. No numerical result available in the reviewed summary. | Warm cache: **60/60 repeated responses served as cache hits**; p50 **11.44 ms**. Coalescing saved **19 calls per 20-request burst**. No geographic data or runoff-simulation workload. | **Conceptually related, not numerically comparable.** Both employ data reuse, but the project has no geographic workload and does not measure geographic computation or data-access efficiency. |
| **9. Exploring the impact of chaos engineering with various user loads on cloud native applications: an exploratory empirical study**. *Computing* 106(7), 2389–2425 (2024). [DOI](https://doi.org/10.1007/s00607-024-01292-z) | Injects delays into serverless and containerized applications under varying load. Measures latency, throughput, availability, error behavior, and recovery. Reports latency increases and availability issues at some injected-delay stress levels; numeric values were not available in the reviewed summary. | Normal-operation baseline only: direct 180/180 HTTP 200; gateway passthrough 179/180 HTTP 200 and one HTTP 502. Gateway latency/throughput measured as above. No delay/failure injection, recovery, or availability-under-fault test. | **Baseline metric overlap, no chaos comparison.** The single 502 was incidental and its cause unknown, not a fault-injection result. The gateway's resilience and recovery are untested. |
| **10. AI-Powered API Gateways for Adaptive Rate Limiting and Threat Detection**. *International Journal of Artificial Intelligence, Data Science, and Machine Learning*. [DOI](https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112) | Proposed anomaly detection, request profiling, and reinforcement-learning-oriented policy adaptation. Measures/claims anomaly-detection effectiveness, adaptive-policy response, and security performance; accessible summary gives no reproducible quantitative baseline or numeric outcome. | Deterministic token-bucket burst: **15 accepted / 5 denied out of 20** in every run, matching initial capacity 15. No anomaly detector, threat-classification measure, ML/RL baseline, or adaptation-response trial. | **Not directly comparable.** The project validates a static initial bucket burst, while the paper proposes intelligent detection/adaptation. The gateway result is a reproducible heuristic baseline, not evidence of better adaptive control or threat detection. |

## 4. Findings

1. **Cache reuse:** the gateway returned a cache hit on all 60 repeated warm
   requests in each run. This demonstrates that the configured response-cache
   path operated for the tested URL and TTL.
2. **Duplicate suppression:** with 20 identical simultaneous GET requests and
   no cache hits, one upstream call was made and 19 were saved in every run.
   This is a measured 95% reduction in upstream calls for this specific
   single-process burst.
3. **Rate-limit enforcement:** 15 requests were accepted and five rejected
   for each 20-request initial-bucket burst, matching the configured capacity.
   This does not establish accuracy under sustained traffic or adaptive
   policy changes.
4. **Passthrough overhead in this test:** gateway passthrough had lower median
   throughput and higher median p50/p95 latency than direct calls to the local
   simulator. The experiment therefore does not support a general gateway
   speed advantage.
5. **No direct overall ranking of the ten papers:** the papers use different
   workloads, platforms, measurement layers, and outcomes. Only the functional
   observations above are defensible for this local gateway test; cross-paper
   numeric superiority is not.

## 5. Limitations

- Only three repeated runs were collected, with substantial run-to-run
  variation. No confidence intervals, significance tests, or separate
  warm-up phase were used.
- The test ran on one workstation; hardware and container resource limits
  were not recorded.
- CPU, memory, sustained rate-limit refill behavior, adaptive QPS response,
  fault recovery, cache invalidation correctness, multi-replica coalescing,
  and real-provider cost were not measured.
- The simulator's 50 ms delay and USD 0.50 per-call charge are artificial.
- Some literature metrics above come from the supplied paper review or
  accessible abstracts rather than verified full-text reanalysis. Numeric
  figures explicitly noted as unconfirmed should be checked against the
  original paper before formal publication.

## References

1. “Impacts of data consistency levels in cloud-based NoSQL for data-intensive
   applications.” *Journal of Cloud Computing* (2024).
   [https://doi.org/10.1186/s13677-024-00716-7](https://doi.org/10.1186/s13677-024-00716-7)
2. “Understanding security tactics in microservice APIs using annotated
   software architecture decomposition models – a controlled experiment.”
   *Empirical Software Engineering* (2025).
   [https://doi.org/10.1007/s10664-024-10601-1](https://doi.org/10.1007/s10664-024-10601-1)
3. “Performance and Availability Analysis of API Design Techniques for API
   Gateways.” *Arabian Journal for Science and Engineering* (online 2024).
   [https://doi.org/10.1007/s13369-024-09474-9](https://doi.org/10.1007/s13369-024-09474-9)
4. “Cache invalidation based on a declarative approach for separating
   business logic of microservices from cache update rules.”
   *Eastern-European Journal of Enterprise Technologies* (2025).
   [https://doi.org/10.15587/1729-4061.2025.325932](https://doi.org/10.15587/1729-4061.2025.325932)
5. “Performance Analysis of NoSQL Databases: MongoDB Document Store and Redis
   Key-Value Store in Microservices-Based Applications Using Flask.”
   *International Journal Software Engineering and Computer Science* (2025).
   [https://doi.org/10.35870/ijsecs.v5i2.4206](https://doi.org/10.35870/ijsecs.v5i2.4206)
6. “Examination of the performance and scalability of a web application in a
   reactive and imperative approach using the Spring Framework.” *Journal of
   Computer Sciences Institute* 32 (2024), 210–216.
   [https://doi.org/10.35784/jcsi.6291](https://doi.org/10.35784/jcsi.6291)
7. “Enhancing Monitoring Performance: A Microservices Approach to Monitoring
   with Spyware Techniques and Prediction Models.” *Sensors* 24(13), 4212
   (2024).
   [https://doi.org/10.3390/s24134212](https://doi.org/10.3390/s24134212)
8. “Research on Service-Oriented Sharing and Computing Framework of
   Geographic Data for Geographic Modeling and Simulation.” *Applied
   Sciences* 14(24), 11983 (2024).
   [https://doi.org/10.3390/app142411983](https://doi.org/10.3390/app142411983)
9. “Exploring the impact of chaos engineering with various user loads on
   cloud native applications: an exploratory empirical study.” *Computing*
   106(7), 2389–2425 (2024).
   [https://doi.org/10.1007/s00607-024-01292-z](https://doi.org/10.1007/s00607-024-01292-z)
10. “AI-Powered API Gateways for Adaptive Rate Limiting and Threat Detection.”
    *International Journal of Artificial Intelligence, Data Science, and
    Machine Learning*.
    [https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112](https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112)
