<!-- prettier-ignore-start -->

-   benchmarking/observability
    -   use [SME validated O Series dataset]
    -   RAGAS: https://docs.ragas.io/en/latest/concepts/metrics/index.html
        -   implement ragas framework in codebase
        -   set up basic ragas notebook on "input data"
-   graph vs vector and approaches
    -   offline (ingest time)
        -   graph
            -   construct a small graph using [an easy to use graph db] that uses a human-readable format (e.g., cypher, gremlin, etc.)
        -   vector
    -   online (query time) - @Logan
        -   graph
            -   construct graph using [in-memory graph db]
        -   k means clustering
            -   construct tree using recursive clustering
-   test scenario
    -   all approaches measured against the same dataset ([SME validated O Series dataset])
-   test suite
    -   for each question, the following tests will be run:
        -   run time
        -   LLM-facilitated accuracy score
        -   cost? (\( tokens * \$/token \)) 
        -   ...William

<!-- prettier-ignore-end -->

## Backlog

| Story                     | Description                                                                  | DRI       |
| ------------------------- | ---------------------------------------------------------------------------- | --------- |
| Online Graph              | Construct graph using [in-memory graph db]                                   | [Logan]   |
| Online K Means Clustering | Construct tree using recursive clustering                                    | [Logan]   |
| Evaluating LLM            | RAGAS: ...                                                                   | [William] |
| Evaluating Search: Vector | Cosine sim/ Euclidean distance between Ground truth chunk and chunk returned | [William] |
| Evaluating Search: Graph  | Graph                                                                        |

<!--links-->

[SME validated O Series dataset]: https://github.com/vertexinc/vtx-copilot/blob/develop/assets/smes/bank-O%20Series%20Cloud.json
[in-memory graph db]: https://ruruki.readthedocs.io/en/master/readme.html#introduction-to-ruruki-in-memory-directed-property-graph
[ml flow]: https://mlflow.org/
[Logan]: https://github.com/loganpowell
[William]: https://github.com/mountaingoatvx
