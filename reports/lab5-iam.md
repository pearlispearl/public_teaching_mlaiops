# Lab 5, Task 2: least privilege

Project `itcs355-6688015`, region `asia-southeast1`, bucket `gs://itcs355-6688015`.

## Identities

Three identities, each with one job.

| Identity | Used by | Permission | Scope | Why it is needed |
|---|---|---|---|---|
| `lab2train` (training) | Every pipeline step and the training jobs | `roles/aiplatform.user` | project | Create custom jobs, upload the model to the registry, create the endpoint |
| | | `roles/storage.objectUser` | **bucket** | Steps hand data to each other under `BLOB_URI/pipeline/<run>/`: read, write, overwrite |
| | | `roles/iam.serviceAccountUser` | on `itcs355-serve` only | `deploy_staging` starts the endpoint as the serving identity, so it must be allowed to act as it |
| | | `roles/artifactregistry.reader`, `roles/monitoring.metricWriter` | project | Carried over from Lab 2. Not re-tested in Lab 5; candidates for removal |
| `itcs355-serve` (serving) | The Vertex endpoint and the Cloud Run service | `roles/storage.objectViewer` | **bucket** | Download `model.joblib` at start-up. Read only |
| | | `roles/logging.logWriter` | project | Write request logs |
| | | `roles/monitoring.metricWriter` | project | Emit the service metrics from Lab 4 |
| `gh-deployer` (CI) | GitHub Actions through Workload Identity Federation | `roles/artifactregistry.writer` | project | Push the serving image |
| | | `roles/run.admin` | project | Create and update the Cloud Run service |
| | | `roles/aiplatform.user` | project | Trigger the pipeline |
| | | `roles/iam.serviceAccountUser` | on `itcs355-serve` and `lab2train` only | Deploy Cloud Run as the serving identity and submit the pipeline as the training identity |

## What was wrong before

* `lab2train` held `roles/storage.objectAdmin` on the whole project: read, write and **delete** in every bucket.
* `gh-deployer` held `roles/iam.serviceAccountUser` on the whole project, so it could act as any service account,
  including the default compute account, which has `roles/editor`. That is editor access by a detour.
* There was no serving identity. The Cloud Run service ran as the default compute account.

## Setup commands

```
gcloud iam service-accounts create itcs355-serve --display-name="Lab 5 serving" --project itcs355-6688015

gcloud storage buckets add-iam-policy-binding gs://itcs355-6688015 --member=serviceAccount:itcs355-serve@itcs355-6688015.iam.gserviceaccount.com --role=roles/storage.objectViewer
gcloud projects add-iam-policy-binding itcs355-6688015 --member=serviceAccount:itcs355-serve@itcs355-6688015.iam.gserviceaccount.com --role=roles/logging.logWriter --condition=None
gcloud projects add-iam-policy-binding itcs355-6688015 --member=serviceAccount:itcs355-serve@itcs355-6688015.iam.gserviceaccount.com --role=roles/monitoring.metricWriter --condition=None

gcloud projects add-iam-policy-binding itcs355-6688015 --member=serviceAccount:gh-deployer@itcs355-6688015.iam.gserviceaccount.com --role=roles/aiplatform.user --condition=None
gcloud iam service-accounts add-iam-policy-binding itcs355-serve@itcs355-6688015.iam.gserviceaccount.com --member=serviceAccount:gh-deployer@itcs355-6688015.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser
gcloud iam service-accounts add-iam-policy-binding lab2train@itcs355-6688015.iam.gserviceaccount.com --member=serviceAccount:gh-deployer@itcs355-6688015.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser

gcloud iam service-accounts add-iam-policy-binding itcs355-serve@itcs355-6688015.iam.gserviceaccount.com --member=serviceAccount:lab2train@itcs355-6688015.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser
```

The last command lets the pipeline's own identity start the endpoint as the serving identity.

## Experiment: remove a permission believed to be unnecessary

**Hypothesis.** The project-wide `storage.objectAdmin` on `lab2train` is far more than the pipeline needs. With it
gone the pipeline should still be able to read (it already had `objectViewer` on the bucket) but not write.

**Action.**

```
gcloud projects remove-iam-policy-binding itcs355-6688015 --member=serviceAccount:lab2train@itcs355-6688015.iam.gserviceaccount.com --role=roles/storage.objectAdmin
IMAGE_TAG=16edcde python scripts/run_pipeline.py --submit --wait
```

**What broke.** Run `itcs355-training-pipeline-20261022215123` failed with 0 of 7 steps completed, before any container
started. Error text in `reports/lab5-iam-break.txt`, screenshot `reports/lab5-task2-iam-break.png`:

> Failed to create pipeline job. Error: Service account `lab2train@itcs355-6688015.iam.gserviceaccount.com` does not
> have `[storage.objects.create]` IAM permission(s) to the bucket "itcs355-6688015".

**Fix.** Granted the narrower role on the bucket only:

```
gcloud storage buckets add-iam-policy-binding gs://itcs355-6688015 --member=serviceAccount:lab2train@itcs355-6688015.iam.gserviceaccount.com --role=roles/storage.objectUser
```

**Confirmation.** With the project-wide `objectAdmin` still removed, run `itcs355-training-pipeline-20261022230508`
completed all steps and the endpoint it deployed ran as `itcs355-serve`
(`reports/lab5-endpoint-describe.yaml`, field `serviceAccount`). So the project-wide grant was not needed. The bucket
grant was.

## What it taught

1. The boundary fell where predicted: reading kept working, creating did not. The error named the single missing
   permission, `storage.objects.create`, not a general "access denied".
2. I expected the first step to fail. The failure came earlier: Vertex checks that the service account can write to the
   pipeline root before it starts any step, so a missing write permission shows up as a job that never starts, not as a
   step that crashes.
3. Not every failure is a permission. Two earlier attempts failed for other reasons (an image tag that did not exist,
   and a model server that could not load a model trained with a newer scikit-learn than its container's). Reading the
   error text before touching IAM saved changing the wrong thing.

## Clean-up commands and how to verify

Run after the last pipeline run and when merging, since removing them earlier can break a run or the deploy:

```
gcloud projects remove-iam-policy-binding itcs355-6688015 --member=serviceAccount:gh-deployer@itcs355-6688015.iam.gserviceaccount.com --role=roles/iam.serviceAccountUser
gcloud storage buckets remove-iam-policy-binding gs://itcs355-6688015 --member=serviceAccount:lab2train@itcs355-6688015.iam.gserviceaccount.com --role=roles/storage.objectViewer
```

The first removes the project-wide right to act as any account; the deploy keeps working through the two
service-account-level grants above. The second removes a grant that `objectUser` already covers.

Verify the final state:

```
gcloud projects get-iam-policy itcs355-6688015 --flatten="bindings[].members" --filter="bindings.members:serviceAccount:lab2train OR bindings.members:serviceAccount:itcs355-serve OR bindings.members:serviceAccount:gh-deployer" --format="table(bindings.members,bindings.role)"
gcloud storage buckets get-iam-policy gs://itcs355-6688015
gcloud iam service-accounts get-iam-policy itcs355-serve@itcs355-6688015.iam.gserviceaccount.com
gcloud iam service-accounts get-iam-policy lab2train@itcs355-6688015.iam.gserviceaccount.com
```

## Residual risks, accepted

* The default compute service account still holds `roles/editor` (granted by Google when the project was created).
  Nothing in this system runs as it any more, but it is still there.
* `roles/run.admin` is broader than a deploy needs; `roles/run.developer` is the narrower candidate and was not tried.
* `artifactregistry.reader` and `monitoring.metricWriter` on `lab2train` were not removed or tested.

## AWS identities (Task 4, Part B)

| Identity | Used by | Permissions | Why that much |
|---|---|---|---|
| `itcs355-lab5` (IAM user, access key on my laptop) | `cloudlayer/aws.py`, `push_image`, the demo | Customer-managed policy `itcs355-lab5-operator`: `s3:ListBucket` on one bucket, `s3:GetObject`/`PutObject` on its objects, `ecr:GetAuthorizationToken` (`*`, AWS does not allow narrowing it) and push/pull actions on one ECR repository | Only what upload, download and image push need. No delete, no Lambda, no IAM |
| `itcs355-lab5-lambda` (execution role of the function) | the serving container at runtime | `itcs355-lab5-model-reader` (`s3:GetObject` on `itcs355/models/*` of one bucket) and `AWSLambdaBasicExecutionRole` (write logs) | The service only reads its model. It cannot write to the bucket |
| console account (root-level, human) | creating the bucket, repository, policies, role, function; Function URL permissions; deleting everything at teardown | full | Kept out of any script, used by hand |

Observed boundary: calling `lambda:UpdateFunctionCode` as `itcs355-lab5` was refused
("no identity-based policy allows the lambda:UpdateFunctionCode action"), which is the intended result: the key on
my laptop can move data and push an image but cannot deploy or change code. I did that step in the console account.

Accepted exposure: during the demo the Function URL used auth type NONE (public), with a resource policy limited to
invocation through the URL. I deleted the URL right after capturing the evidence.

Clean-up at teardown: delete the function, the ECR repository, the bucket, the two policies, the role, and the user's
access key and user. Check the account is empty in the console.
