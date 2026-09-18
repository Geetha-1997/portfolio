# AWS DevOps Portfolio — Complete Build Notes

**What this project is:** A personal portfolio site hosted on Amazon S3, deployed
automatically via a GitHub Actions CI/CD pipeline, with a serverless "contact me"
form (API Gateway → Lambda → DynamoDB → SNS) defined entirely as Infrastructure
as Code using AWS SAM.

**Architecture:**
```
 Visitor's browser
        │
        ▼
 S3 static website  ───────────────►  index.html (portfolio page)
        │
        │ (contact form submit)
        ▼
 API Gateway (HTTP API)
        │
        ▼
 Lambda (contact_handler.py)
        │
        ├──► DynamoDB (logs every submission)
        └──► SNS Topic ──► Email notification to owner

 GitHub repo ──push to main──► GitHub Actions ──► aws s3 sync ──► S3 bucket
```

**Tech used:** AWS S3, Lambda, API Gateway, DynamoDB, SNS, IAM, CloudFormation
(via AWS SAM), GitHub, GitHub Actions.

---

## Prerequisites

- Windows 10/11 with `winget` (check: `winget --version`)
- An AWS account (pay-as-you-go is fine — this project stays inside free-tier limits)
- A GitHub account
- VS Code (or any editor)

---

## Step 0 — Install tooling

```powershell
winget install -e --id Amazon.AWSCLI
winget install -e --id Git.Git
winget install -e --id Amazon.SAM-CLI
```

Close and reopen your terminal (PATH needs to refresh), then verify:
```powershell
aws --version
git --version
sam --version
```

> **Gotcha:** if `sam --version` isn't recognized even after reopening the terminal
> panel, fully restart VS Code (not just the terminal). Winget-installed PATH
> updates sometimes only propagate on a full app restart.

---

## Step 1 — Create your personal IAM user (for CLI use)

Never use your AWS **root** account for daily work — create an IAM user instead.

1. AWS Console → **IAM** → **Users** → **Create user**
2. Username: e.g. `geetha` — leave console access unchecked (CLI-only)
3. **Attach policies directly** → `AdministratorAccess` (fine for a personal
   learning account; scope this down later if working in a team account)
4. Create user → open it → **Security credentials** tab → **Create access key**
   → use case **Command Line Interface (CLI)** → copy both values

Connect the CLI:
```powershell
aws configure
```
Enter your Access Key ID, Secret Access Key, region (e.g. `ap-south-1`), and
output format `json` when prompted.

Verify:
```powershell
aws sts get-caller-identity
```
Should print your Account ID, User ID, and ARN.

> **IAM users, roles, and access keys are always free** — no matter which AWS
> account plan you're on. You're only billed for resources you actually run
> (S3 storage, Lambda invocations, etc.), not for identities.

---

## Step 2 — Project folder structure

Create this structure locally (this is what SAM and GitHub Actions expect —
flat files in the wrong place will break the build):
```
portfolio/
├── index.html
├── template.yaml
├── bucket-policy.json
├── .gitignore
├── lambda/
│   └── contact_handler.py
└── .github/
    └── workflows/
        └── deploy-site.yml
```

```powershell
New-Item -ItemType Directory -Path lambda
New-Item -ItemType Directory -Path .github\workflows
```

Create `.gitignore` in the project root:
```
.aws-sam/
samconfig.toml
```

> **Gotcha:** make sure `.gitignore` is created as a sibling of `index.html`,
> not accidentally nested inside the `.git` folder (easy mistake in some
> editors' "New File" context menus — check the breadcrumb path before saving).

---

## Step 3 — Create and configure the S3 bucket (static hosting)

Bucket names must be globally unique across all AWS accounts — pick something
distinctive.

```powershell
aws s3 mb s3://your-unique-bucket-name --region ap-south-1
aws s3 website s3://your-unique-bucket-name --index-document index.html
```

**Unblock public access** (Console, not CLI):
S3 → your bucket → **Permissions** tab → **Block public access (bucket settings)**
→ Edit → uncheck all 4 boxes → Save → type `confirm`

**Bucket policy** — create `bucket-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::your-unique-bucket-name/*"
  }]
}
```
Apply it:
```powershell
aws s3api put-bucket-policy --bucket your-unique-bucket-name --policy file://bucket-policy.json
```

> **Gotcha:** if this fails with `MalformedPolicy... first byte must be '{'`,
> your editor likely saved the JSON file with a UTF-8 BOM (invisible bytes at
> the start of the file). Fix: in VS Code, click the encoding indicator in the
> bottom status bar → **Save with Encoding** → **UTF-8** (without BOM).

---

## Step 4 — First manual deploy

```powershell
aws s3 sync . s3://your-unique-bucket-name `
  --exclude ".git/*" --exclude "lambda/*" --exclude "template.yaml" `
  --exclude "README.md" --exclude ".github/*" --exclude "bucket-policy.json"
```

Visit your site:
```
http://your-unique-bucket-name.s3-website.ap-south-1.amazonaws.com
```
(Note the endpoint format varies by region: newer regions like `ap-south-1`
use `s3-website.<region>.amazonaws.com`; older regions like `us-east-1` use
`s3-website-<region>.amazonaws.com`, with a dash instead of a dot.)

---

## Step 5 — Deploy the serverless contact-form backend

`template.yaml` (AWS SAM) defines: API Gateway → Lambda → DynamoDB + SNS.
`lambda/contact_handler.py` is the function code — see the repo for the full
source; in short, it validates the form input, writes a record to DynamoDB,
then publishes a notification to SNS.

Build and deploy:
```powershell
sam build
sam deploy --stack-name portfolio-contact-backend --region ap-south-1 `
  --parameter-overrides NotificationEmail=you@example.com AllowedOrigin="*" `
  --capabilities CAPABILITY_IAM --resolve-s3 --no-confirm-changeset
```

> **Gotcha:** `sam deploy --guided` (the interactive version) can occasionally
> inject a stray leading space into the stack name from the prompt, which
> then fails with a cryptic `CompanionStack` `ValidationError`. Deploying with
> explicit flags (as above) avoids the interactive prompt entirely and sidesteps
> the issue.

**Confirm the SNS email subscription** — check your inbox for an email from
AWS titled "AWS Notification - Subscription Confirmation" and click **Confirm
subscription**. Submissions won't reach you until this is done.

**Copy the API URL** from the deploy output's `Outputs` section
(`ContactApiUrl`), and paste it into `index.html`, replacing the
`CONTACT_API_URL` placeholder near the bottom of the `<script>` block.

Re-sync the updated file:
```powershell
aws s3 cp index.html s3://your-unique-bucket-name/index.html
```

---

## Step 6 — Push the code to GitHub

```powershell
git init
git add .
git status   # sanity check: confirm .aws-sam/ is NOT listed, nothing sensitive staged
git commit -m "Initial commit: portfolio site, contact backend, CI/CD pipeline"
git branch -M main
```

Create an empty repo on github.com (no README/license — you already have your own),
then:
```powershell
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
git push -u origin main
```

---

## Step 7 — Set up the GitHub Actions CI/CD pipeline

**Create a separate, least-privilege IAM user just for GitHub Actions** — don't
reuse your personal admin credentials here.

1. IAM → Users → Create user → `github-actions-deploy` → no console access
2. Open the user → Permissions → **Add permissions** → **Create inline policy**
   → JSON tab:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::your-unique-bucket-name",
        "arn:aws:s3:::your-unique-bucket-name/*"
      ]
    }
  ]
}
```
   Name it `deploy-portfolio-s3` → Create policy
3. **Security credentials** tab → **Create access key** → use case **CLI** →
   copy both values

**Add them as GitHub repo secrets/variables**
Repo → **Settings** → **Secrets and variables** → **Actions**:

Variables tab (3):
| Name | Value |
|---|---|
| `USE_OIDC` | `false` |
| `AWS_REGION` | `ap-south-1` |
| `S3_BUCKET_NAME` | `your-unique-bucket-name` |

Secrets tab (2):
| Name | Value |
|---|---|
| `AWS_ACCESS_KEY_ID` | access key from above |
| `AWS_SECRET_ACCESS_KEY` | secret key from above |

`.github/workflows/deploy-site.yml` (already in the repo) triggers on every
push to `main` that touches `index.html`, authenticates using those secrets,
and runs `aws s3 sync` automatically.

**Trigger it manually the first time:** repo → **Actions** tab → select the
workflow → **Run workflow**. After that, every push to `main` triggers it
automatically.

**Test the automation for real:** edit `index.html`, then:
```powershell
git add index.html
git commit -m "Update content"
git push
```
Watch the Actions tab — a new run should start automatically without any
manual trigger.

---

## Step 8 — Set an AWS Budget (do this early, not last)

Console → **Billing and Cost Management** → **Budgets** → **Create budget**
→ **Cost budget** (not Savings Plans or Reservation — easy to pick the wrong
type, the list has several similarly-named options) → Monthly → set an
amount (e.g. $5) → add alert thresholds (80% actual, 100% forecasted) → your
email → Create.

This is a monitoring/alert system, not a spending cap — it won't stop
resources automatically, but you'll get an email warning before costs
become a problem.

---

## Cost reality check

Everything in this project (S3, Lambda, API Gateway, DynamoDB, SNS) is
pay-per-use with generous always-free or 12-month-free allowances. A
portfolio site with light contact-form traffic realistically costs **$0/month**.
The only way to actually spend money is leaving unrelated resources (EC2,
NAT gateways, RDS) running — nothing in this stack does that.

---

## Cleanup / teardown (when you're done testing)

```powershell
# 1. Delete the backend stack (removes Lambda, API Gateway, DynamoDB, SNS, IAM role)
sam delete --stack-name portfolio-contact-backend --region ap-south-1

# 2. Empty and delete the site bucket
aws s3 rm s3://your-unique-bucket-name --recursive
aws s3 rb s3://your-unique-bucket-name
```

> **Gotcha:** SAM's own managed deployment bucket
> (`aws-sam-cli-managed-default-samclisourcebucket-xxxxx`) is a separate
> bucket it creates automatically and does **not** get removed by `sam delete`.
> If you want a fully clean account, delete it too. It has versioning enabled,
> so a plain `aws s3 rm --recursive` won't fully empty it — you need to purge
> object versions and delete markers first:
> ```powershell
> $bucket = "aws-sam-cli-managed-default-samclisourcebucket-xxxxx"
> $versions = aws s3api list-object-versions --bucket $bucket --output json | ConvertFrom-Json
> foreach ($v in $versions.Versions)      { aws s3api delete-object --bucket $bucket --key $v.Key --version-id $v.VersionId }
> foreach ($m in $versions.DeleteMarkers) { aws s3api delete-object --bucket $bucket --key $m.Key --version-id $m.VersionId }
> aws s3 rb s3://$bucket
> ```
> It'll be recreated automatically next time you run `sam deploy` on any project.

**Also check for an orphaned SNS subscription** — if you deleted the stack
before clicking "Confirm subscription" in your email, a "Pending confirmation"
row can linger in SNS → Subscriptions. It's harmless (expires on its own,
costs nothing) but delete it manually for a fully clean sweep.

**Final verification checklist:**
- [ ] Lambda → no functions
- [ ] API Gateway → no APIs
- [ ] DynamoDB → no tables
- [ ] SNS → no topics, no orphaned subscriptions
- [ ] CloudFormation → Stacks (0)
- [ ] S3 → no buckets
- [ ] Billing → Cost Explorer shows $0 / near-$0 month-to-date (allow ~24h for
      data to populate on a fresh account)

---

## Common issues encountered (and fixes)

| Symptom | Cause | Fix |
|---|---|---|
| `MalformedPolicy` on `put-bucket-policy` | JSON file saved with UTF-8 BOM | Re-save as UTF-8 without BOM |
| `sam deploy --guided` fails with `CompanionStack` `ValidationError` | Stray whitespace captured in interactive stack-name prompt | Deploy with explicit `--stack-name` flag instead of `--guided` |
| Files uploaded to S3 that shouldn't be there (`.yml`, `.py` in bucket root) | Project files were flat instead of in `lambda/` and `.github/workflows/` | Move files into correct subfolders before syncing |
| `.gitignore` not excluding `.aws-sam/` | File accidentally created inside `.git/` instead of project root | Recreate it as a sibling of `index.html` |
| `BucketNotEmpty` when deleting SAM's managed bucket | Bucket has versioning enabled; old versions + delete markers remain after a normal `rm` | Purge all object versions and delete markers first, then delete the bucket |
| Contact form submissions never arrive | SNS email subscription never confirmed | Check inbox for AWS confirmation email, click confirm |
