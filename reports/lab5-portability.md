# Lab 5, Task 4 Part C: portability write-up

## What I did

Part A: `make portability-audit` passes; no provider string appears in `src/`, `service/`, `monitoring/` or `tests/`.

Part B: a second adapter, `cloudlayer/aws.py`, with `upload`, `download` and `invoke` (plus `push_image`, because the
interface requires it to instantiate the class; it is untested). Four offline tests (`cloudlayer/test_aws_adapter.py`)
pass without an AWS account, using a fake S3 and a stubbed SageMaker call. `make swap-check SECOND=aws` against an S3
emulator gave: upload PASS, download PASS, invoke FAIL (no model server behind it).
**UPDATE after the run on a real AWS account: paste the three outcomes here. Until then the claim is limited to
the offline result above.**

## Which method was hardest, and why

`invoke`. `upload` and `download` map one to one (put an object, get an object); the only work was parsing
`BLOB_URI` and creating parent directories. `invoke` is where the platforms stop agreeing. On GCP I look an
endpoint up by display name, turn it into an id, and call `:rawPredict` with a bearer token. On AWS the endpoint is
named, the call goes through a separate runtime client, and the container behind it must serve `POST /invocations`
and `GET /ping` on port 8080. Our service answers `/predict` and `/ready`. It is also the one method I could not
test for real, because it needs a running endpoint, which costs money.

## One place the abstraction leaked and could not be hidden

The serving container contract. On Vertex the Model resource declares the routes (`/predict`, `/ready`, port 8080), so
the same image works unchanged. SageMaker fixes the routes. The Lab 3 `Dockerfile.serve` already says this in a
comment: absorb the difference in `cloudlayer/` or map the paths in the image, and do not rename the routes in
`service/app.py`. An adapter cannot do it from the outside; the image needs a shim for `/invocations` and `/ping`. The
interface has eleven methods and none of them is "the shape of the container".

Smaller leaks I met on the way: switching provider is not one variable. `BLOB_URI`, `CONTAINER_REGISTRY` and
`IDENTITY_REF` are all provider-shaped, so `cloud.env` has to change as a set (the swap check reuses one config object, so
I had to export `BLOB_URI` to an `s3://` value to run it). And the pipeline compiler is outside the seam altogether:
`compile_gcp` is about 100 lines of Kubeflow, with two limits (spot VMs are not applied, one condition per pipeline), and
SageMaker Pipelines or Azure ML would each need their own.

## What a full migration would cost

My estimate, not a measurement: about 25 engineering days for one person.

| Area | Days |
|---|---|
| Storage, registry and the lineage metadata | 2.5 |
| Training jobs | 3 |
| Pipeline compiler and conditions | 5 |
| Endpoints and the serving container contract | 3 |
| Metrics and alerts | 2 |
| Identities and permissions | 3 |
| CI/CD with federated identity | 2 |
| Managed LLM call, teardown, cost reporting | 2.5 |
| Testing and debugging against the real platform | 3 |

The pipeline and the permission model dominate, and neither is behind the eleven methods.

## Was the abstraction worth building?

Partly, and not for the reason it was built. As a way to move between clouds, no: writing three of eleven methods
touched the cheap part, the expensive parts (pipelines, permissions, the serving contract) sit outside the interface,
and this project has one provider and one student, so the option to leave was never used. What did pay off: the
adapter made it possible to test cloud code offline (a fake S3 and a stub) with no account and no bill, and the
audit made me keep provider names out of the logic I wanted to reason about. If I had to do it again for one provider
I would keep the adapter for those two reasons and would not spend time on the second one.
