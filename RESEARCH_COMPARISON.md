# Research Comparison: Intelligent API Gateway

## Executive summary

The strongest defensible contribution is **integration**, not a demonstrated
numerical win over the cited papers. This project combines API-key
authentication, Redis-backed token-bucket rate limiting, Redis response
caching with stale-while-revalidate (SWR), in-flight request coalescing, a
deterministic per-key rate adjustment loop, and Prometheus instrumentation in
one asynchronous gateway request path.

The ten papers study different systems, workloads, and outcomes. Their results
cannot be ranked against this gateway without reproducing compatible workloads
and baselines. In particular, do not claim that this gateway is faster than a
paper's database, protocol, framework, or monitoring system based on the
current project evidence.

## What this project actually implements

The current request path in [gateway/main.py](./gateway/main.py) is:

1. Metrics (outermost)
2. API-key authentication
3. Rate limiting
4. Response cache
5. Request coalescing
6. Route / downstream service

Relevant implementation details:

- API-key metadata is stored in Redis; authentication fails closed if the
  repository is unavailable ([gateway/auth/repository.py](./gateway/auth/repository.py),
  [gateway/auth/middleware.py](./gateway/auth/middleware.py)).
- Rate limiting uses a Redis Lua token bucket. A background analyzer adjusts
  per-key QPS deterministically: it reduces QPS when the ratio of one-second
  request rate to the 60-second average exceeds 2.0, and increases it when the
  ratio is below 1.2, subject to a 10-second cooldown and configured hard cap
  ([gateway/ratelimit/limiter.py](./gateway/ratelimit/limiter.py),
  [gateway/analyzer/processor.py](./gateway/analyzer/processor.py)).
- The response cache is Redis-backed and supports fresh hits, SWR stale hits,
  and a Redis lock for background refresh
  ([gateway/cache/middleware.py](./gateway/cache/middleware.py),
  [gateway/cache/manager.py](./gateway/cache/manager.py)).
- Request coalescing deduplicates matching in-flight GETs, but its flight table
  is **in process memory**, not shared across gateway workers or replicas
  ([gateway/coalescer/manager.py](./gateway/coalescer/manager.py)).
- Prometheus instrumentation includes request counts and latency, cache
  outcomes, rate-limit denials, upstream calls, coalescing, and simulated cost
  ([gateway/metrics/collector.py](./gateway/metrics/collector.py)).
- The local paid-API simulator defaults to a 50 ms delay; this is a controlled
  test fixture, not a result for a production provider
  ([simulator/main.py](./simulator/main.py)).

## Paper-by-paper comparison

| # | Paper's scope and reported evidence | Valid comparison with this gateway | What we can claim—and what we cannot |
|---|---|---|---|
| 1 | Compares MongoDB, Cassandra, and Redis consistency settings in cloud and multi-region workloads; performance varies by database, operation, and consistency configuration. [Source](https://doi.org/10.1186/s13677-024-00716-7) | The gateway uses Redis for API-key state, rate-limit buckets, and response cache, bringing state operations into the request path rather than treating the database as the whole subject. | **Can claim:** this project evaluates Redis as a component of a gateway policy stack. **Cannot claim:** better Redis throughput, stronger consistency, or lower latency than the paper. Its reported setup is not reproduced here. The user-provided figures of about 4,000 requests/s and 2 ms should be checked against the full paper before citing; they were not confirmed from the accessible abstract. |
| 2 | Controlled experiment on security-annotated architecture decomposition diagrams, involving students and industry experts; reports improved assessment correctness with annotated diagrams. [Source](https://doi.org/10.1007/s10664-024-10601-1) | This gateway enforces runtime API-key authentication and token-bucket traffic control, whereas the study concerns architecture-level security assessment and communication. | **Can claim:** the project implements runtime enforcement points that can be documented in an architecture model. **Cannot claim:** stronger security or better security assessment outcomes; no threat model, security-tactic evaluation, or comparative experiment has been run. |
| 3 | Compares API design techniques for gateways, as identified by its title and bibliographic record. The publisher's abstract and methods were inaccessible during verification. [Source](https://doi.org/10.1007/s13369-024-09474-9) | The project can contribute a different evaluation dimension: how cache, coalescing, authentication, and rate control affect request-path latency and upstream work. | **Can claim:** these are measurable dimensions in this project. **Cannot claim:** superiority over REST, gRPC, Thrift, or any result attributed to the paper until its methods and findings have been read and matched to a compatible test. |
| 4 | Proposes declarative cache-update rules separated from microservice business logic, using asynchronous inter-service updates for cache additions, updates, and deletions. The accessible abstract does not provide quantified comparative results. [Source](https://doi.org/10.15587/1729-4061.2025.325932) | This gateway's cache is a response-path optimization using SWR and a refresh lock; the coalescer can reduce duplicate work on simultaneous misses. | **Can claim:** the project addresses response reuse and concurrent duplicate requests in a gateway. **Cannot claim:** better invalidation correctness or lower cache-management coupling. It does not implement the paper's declarative invalidation rules, and SWR is not a substitute for explicit business-data invalidation. |
| 5 | Compares MongoDB and Redis in Flask microservices for CRUD and aggregation over nested transport data; the abstract reports lower Redis latency for its tested operations. [Source](https://doi.org/10.35870/ijsecs.v5i2.4206) | This project deliberately uses Redis for hot gateway state and response caching rather than presenting Redis and MongoDB as interchangeable application databases. | **Can claim:** a narrower gateway use case and a measurable request-path role for Redis. **Cannot claim:** that this gateway is faster than the paper's database workloads or that Redis is universally preferable; the workloads and roles differ. |
| 6 | Compares reactive and imperative Spring applications, including gateway-context latency and CPU/RAM measurements; the reported advantage depends on operation type and resource. [Source](https://doi.org/10.35784/jcsi.6291) | The gateway uses asynchronous FastAPI handling and an asynchronous HTTP client, so it can test an async gateway request path with stateful middleware. | **Can claim:** asynchronous implementation is part of the design. **Cannot claim:** lower latency, CPU, or RAM than the Spring reactive/imperative variants. This project has not run that controlled framework comparison or collected comparable resource measurements. |
| 7 | Studies organizational monitoring, prediction models, and Spring Boot versus Quarkus. The abstract reports large CPU/RAM differences, but its “uptime decreased by 119%” wording is ambiguous. [Source](https://doi.org/10.3390/s24134212) | This gateway exposes operational counters and latency histograms and uses a simple deterministic traffic analyzer. | **Can claim:** gateway policy effects can be instrumented for a future controlled evaluation. **Cannot claim:** predictive monitoring or lower resource use than the paper's systems. The study is not an API-gateway benchmark, and its reported resource results are not transferable without reproducing its setup. |
| 8 | Proposes a geographic-data sharing and computing framework and validates it with a runoff-simulation case. [Source](https://doi.org/10.3390/app142411983) | Both systems involve service-oriented access to data, but this gateway's focus is request mediation and traffic policy, not geographic computation. | **Can claim:** Redis-backed reuse is consistent with the broader use of in-memory data in service-oriented systems. **Cannot claim:** better geographic-data access, simulation performance, or service sharing; the domains and measured outcomes are different. |
| 9 | Exploratory fault-injection study of two cloud-native applications under user load; injected delays increased latency and exposed availability issues. [Source](https://doi.org/10.1007/s00607-024-01292-z) | Its approach suggests a useful next evaluation for this gateway: vary load while injecting Redis, downstream, and network delay/failure. | **Can claim:** the gateway has observable request and upstream behavior that can be measured under faults. **Cannot claim:** improved availability or resilience. This project has not run chaos experiments or verified recovery behavior under those failures. |
| 10 | Proposes an AI-powered gateway using anomaly detection, request profiles, and reinforcement-learning-oriented policy changes. The accessible abstract does not provide a reproducible baseline or quantitative results. Publication-year metadata is also uncertain. [Source](https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112) | This gateway's adaptive policy is deterministic threshold logic over observed traffic, not ML/RL threat detection. It can provide a simple, inspectable baseline for later adaptive-policy research. | **Can claim:** a transparent heuristic adapts configured QPS within a hard maximum. **Cannot claim:** better threat detection, learning, policy quality, or performance than the proposed AI framework. Those outcomes require an implemented comparable model and controlled evaluation. |

## Strong, defensible positioning for the paper

The project is best positioned as an **integrated, measurable gateway
prototype** that brings several concerns into one runtime path:

- identity checks and per-key traffic control;
- Redis-backed shared policy and response-cache state;
- response caching with SWR and in-flight duplicate suppression;
- deterministic rate adjustment from live request statistics; and
- Prometheus instrumentation for latency, upstream work, cache behavior, and
  denials.

This is a defensible scope distinction from papers that focus on one database
consistency strategy, one cache-invalidation design, one protocol/framework
comparison, architecture-level security assessment, or one monitoring/fault
study. It is not proof that the gateway has a higher throughput or lower
latency than any of them.

### Results that should not be used as evidence

The existing [BENCHMARK_REPORT.md](./BENCHMARK_REPORT.md) reports zero
coalescing reduction, zero rate-limit accuracy, and zero throughput. It also
derives gateway latency from a hard-coded 50 ms simulator baseline plus
instrumented overhead rather than reporting a paired direct-versus-gateway
measurement. Do not quote those figures as verified performance results.

## Measured gateway results

The local Docker Compose stack was rebuilt from the current checkout and
measured in three runs. Each run used 60 requests per latency scenario and a
maximum concurrency of 20. The backend simulator's default processing delay
was 50 ms. Values below are medians across the three runs; the ranges are
included because the run-to-run variance was substantial.

| Scenario | Median observed result | Range across three runs | Interpretation |
|---|---:|---:|---|
| Direct simulator POST, concurrency 20 | 78.08 requests/s; p50 87.07 ms; p95 260.75 ms; p99 500.62 ms | 35.37–120.88 requests/s; p50 81.63–298.50 ms; p95 235.37–883.39 ms | Baseline is the local simulated backend, not a paper's production/cloud deployment. |
| Gateway POST passthrough, concurrency 20 | 51.46 requests/s; p50 348.09 ms; p95 449.30 ms; p99 464.11 ms | 21.05–64.09 requests/s; p50 290.38–924.74 ms; p95 370.00–1,384.42 ms | 179/180 responses were 200 and one was 502. Versus direct simulator, median throughput was 34.09% lower, p50 299.78% higher, and p95 72.31% higher in this exploratory test. This is measured gateway overhead under the tested host/load, not a universal result. |
| Warm response cache | 60/60 requests were `X-Cache: HIT` in every run; median p50 11.44 ms, p95 31.64 ms, p99 36.64 ms | Warm throughput 50.08–84.51 requests/s; p50 8.68–16.13 ms; p95 27.23–36.65 ms | Valid evidence that this configured endpoint serves the repeated URL from cache. Not directly comparable with Redis GET latency in a database benchmark. |
| Fresh identical GET burst | 20 successful responses, 1 upstream call, 19 saved calls per run (95% reduction) | Same outcome in all three runs; p50 216.15–280.55 ms; p95 237.14–307.23 ms | Cache misses were 20 and cache hits 0 in each burst, so the 19-call reduction is attributable to coalescing rather than cache hits. Applies to identical simultaneous GETs in one gateway process. |
| Simulated cost for identical burst | $0.50 observed vs $10.00 for 20 separate simulator calls; $9.50 saved per burst | Same simulator billing assumption in each run | Illustrative cost only: simulator charges a fixed $0.50 per call; it is not a forecast of real provider pricing. |
| Initial-bucket rate-limit burst | Of 20 concurrent requests, 15 returned 200 and 5 returned 429 | Same outcome in all three runs | Matches the configured initial bucket capacity of 15. This validates this burst case, not general rate-limit accuracy across sustained traffic or dynamic adaptation. |

Raw per-run evidence is in [run 1](./research-benchmark-results.json),
[run 2](./research-benchmark-results-2.json), and
[run 3](./research-benchmark-results-3.json); the compact aggregate is
[research-benchmark-summary.json](./research-benchmark-summary.json).

### How the measured results relate to the papers

| Paper | Published outcome / metric described in the reviewed citation | Project measurement | Valid conclusion |
|---|---|---|---|
| 1 — Cloud NoSQL consistency | The supplied paper notes cite Redis up to about 4,000 requests/s and writes near 2 ms in its tested configurations; these exact numbers still need checking against the full paper. | Local gateway: 51.46 POST requests/s median at concurrency 20; warm cached response p50 11.44 ms. | **No performance win established.** The paper measures database operations and consistency configurations in cloud deployments; this gateway measurement includes HTTP, auth, rate-limit, cache/coalescer middleware, container networking, and a simulator. |
| 2 — Security tactics in microservice APIs | Architecture-model security metrics and participant assessment/task outcomes. | 15/20 burst calls allowed and 5/20 denied for the configured token bucket; no security-architecture metric or expert evaluation collected. | This demonstrates one runtime traffic-control case, not improved security tactics or security assessment quality. |
| 3 — API design techniques for gateways | Response time, throughput, and availability across API design/protocol techniques; detailed paper results were unavailable for verification. | Direct and gateway simulator POST throughput and latency as above; no protocol alternatives or availability campaign. | A useful local gateway baseline, but not a comparison of REST/gRPC/Thrift or a claim of superiority. |
| 4 — Declarative cache invalidation | Cache consistency, coupling, and management effectiveness for declarative update rules. | 60/60 repeated warm GETs hit cache; an identical miss burst made one upstream call. | Demonstrates response reuse and request deduplication only. It does not evaluate invalidation correctness or implement the paper's declarative update rules. |
| 5 — MongoDB vs Redis in Flask microservices | The supplied paper summary reports Redis read averages of 0.37 ms and read-by-ID averages of 1.05 ms for its tested workload. | Warm gateway response p50 11.44 ms and p95 31.64 ms. | **The gateway is not faster at this compared measurement.** The numbers are not apples-to-apples: Redis operation latency is not full HTTP gateway response latency; report the level difference, not a head-to-head database conclusion. |
| 6 — Reactive vs imperative Spring | Query time, CPU/RAM, and latency in gateway context. | Gateway end-to-end response latency measured; CPU and RAM were not sampled. | Insufficient evidence to claim a resource or framework advantage. |
| 7 — Monitoring performance | CPU, memory, uptime, and framework comparison. | Prometheus request/cache/coalescing/rate-limit metrics collected; no CPU, RAM, or uptime series collected. | This project demonstrates operational request instrumentation, not monitoring-system efficiency or lower resource usage. |
| 8 — Geographic service-oriented framework | Application-level data-access and simulation effectiveness in a geographic-data use case. | No geographic workload or application-level data access comparison. | Conceptual architecture relevance only; no quantitative comparative claim is valid. |
| 9 — Chaos engineering | Latency, throughput, availability, and recovery under injected faults and changing load. | Normal-operation load and burst tests only; no Redis/backend fault injection. | The gateway has not yet been shown to improve resilience or availability. |
| 10 — AI-powered adaptive gateways | Proposed anomaly detection and adaptive policy; available abstract lacks reproducible quantitative baseline. | Deterministic token-bucket burst behavior observed; 15/20 accepted in each 20-request initial burst. | This is an interpretable heuristic baseline, not a demonstrated improvement over ML/RL threat detection or adaptive rate control. |

The run used a local Docker Compose setup on a Windows workstation. Hardware,
CPU/memory limits, exact Docker resource consumption, confidence intervals,
and warm-up phases were not recorded. One direct/gateway trial had especially
high latency, reflected in the ranges; one gateway request returned 502 and
its underlying downstream error was not determined. Treat the results as an
exploratory project baseline—not a publication-grade benchmark or an
apples-to-apples reproduction of the papers.

## Recommended experiments

Use the same host, container limits, request payloads, and run duration for
each variant. Run warm-ups, repeat each condition at least three times, report
the median across runs, and include p50/p95/p99 latency, throughput, errors,
and CPU/memory where relevant.

1. **Gateway overhead:** compare direct simulator POSTs with gateway POST
   passthrough using the same payload and simulator delay.
2. **Cache effect:** compare the first cold GET with repeated identical warm
   GETs; report `X-Cache`, latency percentiles, and upstream-call deltas.
3. **Coalescing effect:** issue a fresh identical-URL GET burst against an
   empty cache; report incoming requests, `batch_saved_total`,
   `coalesced_requests_total`, cache hits/misses, and upstream calls. Separate
   cache hits from true coalescer savings.
4. **Rate-limit behavior:** use a fresh API key and known bucket capacity/refill
   rate; test both a simultaneous burst and a sustained rate. Compare allowed
   and denied requests with the token-bucket model. Record that the adaptive
   analyzer can change QPS during a run.
5. **Adaptation:** replay stable traffic, a controlled burst, then stable
   traffic again; record QPS changes and recovery time against the configured
   hard cap.
6. **Resilience:** inject Redis and downstream latency/failures and record
   status, latency, recovery, and policy behavior. Do not describe the gateway
   as resilient until these tests pass.
7. **Scaling:** repeat coalescing with multiple gateway workers/replicas. The
   current coalescer is process-local, so report whether duplicates arriving at
   different workers still reach the backend.

The harness in [benchmarks/research_benchmark.py](./benchmarks/research_benchmark.py)
measures direct and gateway passthrough latency, warm-cache behavior, an
identical-GET burst with Prometheus counter deltas, and an observed rate-limit
burst. It is a functional baseline, not a full publication-grade load-testing
suite; use a larger controlled load generator and resource monitoring for final
results.

Example local run:

```powershell
docker compose up -d --build
python benchmarks\research_benchmark.py --iterations 100 --concurrency 20 --output research-benchmark-results.json
```

## References and verification notes

1. “Impacts of data consistency levels in cloud-based NoSQL for data-intensive applications.” *Journal of Cloud Computing* (2024). [DOI](https://doi.org/10.1186/s13677-024-00716-7). Publisher retrieval was blocked; title and abstract were cross-checked against [Crossref](https://api.crossref.org/works?query.title=Impacts%20of%20data%20consistency%20levels%20in%20cloud-based%20NoSQL%20for%20data-intensive%20applications&rows=3) and [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1186/s13677-024-00716-7?fields=title,abstract,year,venue).
2. “Understanding security tactics in microservice APIs using annotated software architecture decomposition models – a controlled experiment.” *Empirical Software Engineering* (2025). [DOI](https://doi.org/10.1007/s10664-024-10601-1); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11828814/).
3. “Performance and Availability Analysis of API Design Techniques for API Gateways.” *Arabian Journal for Science and Engineering*, published online 2024; volume 50, issue 15. [DOI](https://doi.org/10.1007/s13369-024-09474-9). Methods and results were not verified because the publisher abstract was inaccessible.
4. “Cache invalidation based on a declarative approach for separating business logic of microservices from cache update rules.” *Eastern-European Journal of Enterprise Technologies* (2025). [DOI and article](https://doi.org/10.15587/1729-4061.2025.325932).
5. “Performance Analysis of NoSQL Databases: MongoDB Document Store and Redis Key-Value Store in Microservices-Based Applications Using Flask.” *International Journal Software Engineering and Computer Science* (2025). [DOI](https://doi.org/10.35870/ijsecs.v5i2.4206). Publisher retrieval was blocked; detailed setup beyond the indexed abstract remains unverified.
6. “Examination of the performance and scalability of a web application in a reactive and imperative approach using the Spring Framework.” *Journal of Computer Sciences Institute* 32 (2024), 210–216. [DOI and article](https://doi.org/10.35784/jcsi.6291).
7. “Enhancing Monitoring Performance: A Microservices Approach to Monitoring with Spyware Techniques and Prediction Models.” *Sensors* 24(13), 4212 (2024). [DOI](https://doi.org/10.3390/s24134212); [full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC11244305/). The abstract's uptime wording is ambiguous.
8. “Research on Service-Oriented Sharing and Computing Framework of Geographic Data for Geographic Modeling and Simulation.” *Applied Sciences* 14(24), 11983 (2024). [DOI](https://doi.org/10.3390/app142411983).
9. “Exploring the impact of chaos engineering with various user loads on cloud native applications: an exploratory empirical study.” *Computing* 106(7), 2389–2425 (2024). [DOI](https://doi.org/10.1007/s00607-024-01292-z). Publisher retrieval was blocked; the indexed abstract is the basis for the comparison.
10. “AI-Powered API Gateways for Adaptive Rate Limiting and Threat Detection.” *International Journal of Artificial Intelligence, Data Science, and Machine Learning*. [DOI](https://doi.org/10.63282/3050-9262.ijaidsml-v5i4p112); [publisher article](https://ijaidsml.org/index.php/ijaidsml/article/view/273). The DOI resolves, but the publication year was not independently confirmed.
