# Geetha — AWS DevOps Portfolio

A single-page portfolio site (terminal / CI-pipeline theme) with a serverless
"contact me" form, deployed to Amazon S3 through a GitHub Actions CI/CD
pipeline.

```
portfolio/
├── index.html                       # the site itself
├── lambda/
│   └── contact_handler.py           # contact-form backend (Lambda)
├── template.yaml                    # SAM template: API Gateway + Lambda + SNS
└── .github/workflows/
    └── deploy-site.yml              # CI/CD: pushes index.html to S3 on every push
```

---

## 1. Before you start — replace the placeholders

In `index.html`, replace:
- `youremail@example.com`, `github.com/yourusername`, `linkedin.com/in/yourusername`
- The About / Experience / Projects section copy — it's written as a template for you to fill with your real projects, certifications, and background
- `CONTACT_API_URL` (near the bottom of the `<script>`) — you'll get this in step 3

---

## 2. Host the static site on S3

```bash
# 1. Create the bucket (name must be globally unique)
aws s3 mb s3://geetha-portfolio-site --region ap-south-1

# 2. Turn off "block public access" for this bucket (console: Permissions tab),
#    then enable static website hosting
aws s3 website s3://geetha-portfolio-site --index-document index.html

# 3. Attach a bucket policy allowing public reads (bucket-policy.json below)
aws s3api put-bucket-policy --bucket geetha-portfolio-site --policy file://bucket-policy.json

# 4. First upload
aws s3 sync . s3://geetha-portfolio-site --exclude ".git/*" --exclude "lambda/*" --exclude "template.yaml"
```

`bucket-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadGetObject",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::geetha-portfolio-site/*"
  }]
}
```

Your site URL will be:
`http://geetha-portfolio-site.s3-website-<region>.amazonaws.com`

**Optional but recommended:** put CloudFront in front of the bucket for HTTPS,
a custom domain, and caching. Not required to get started.

---

## 3. Deploy the "text me" contact backend

The form on the site needs somewhere to send submissions — S3 alone can't run
backend code. `template.yaml` defines a small serverless stack:

**API Gateway → Lambda → SNS → your email/phone**

```bash
# Install the SAM CLI first: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
sam build
sam deploy --guided
```

During `--guided`, it will ask for `NotificationEmail` — enter your email
address. After deploy:

1. **Confirm the SNS subscription** — check your inbox for an email from AWS
   and click "Confirm subscription" (required once).
2. Copy the `ContactApiUrl` value from the deploy output.
3. Paste it into `index.html` as `CONTACT_API_URL`, then re-sync to S3.

**To also get a text message (SMS)** instead of / in addition to email,
add a second subscription to the SNS topic:
```bash
aws sns subscribe --topic-arn <ContactTopicArn> --protocol sms --notification-endpoint +91XXXXXXXXXX
```

**Every submission is also logged to DynamoDB** (table `portfolio-contact-submissions`),
so nothing is lost if you miss the email/SMS notification. To view submissions:
```bash
aws dynamodb scan --table-name portfolio-contact-submissions
```
or check it visually in the AWS Console → DynamoDB → Tables →
`portfolio-contact-submissions` → Explore table items. It's billed
pay-per-request, so it costs nothing when nobody's submitting the form and
sits comfortably inside DynamoDB's always-free tier for this kind of traffic.

---

## 4. Push the code to GitHub

```bash
cd portfolio
git init
git add .
git commit -m "Initial commit: portfolio site + CI/CD + contact backend"
git branch -M main
git remote add origin https://github.com/yourusername/portfolio.git
git push -u origin main
```

---

## 5. Set up the GitHub Actions deploy pipeline

`deploy-site.yml` syncs `index.html` to S3 automatically on every push to
`main`. It supports two auth methods — **use OIDC**, it's the current AWS/GitHub
recommended practice because no long-lived AWS keys are stored in GitHub.

### Recommended: OIDC (no stored AWS keys)
1. In AWS, create an IAM OIDC identity provider for `token.actions.githubusercontent.com`
   (one-time per account) and an IAM role that trusts your specific repo, with
   an inline policy allowing `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`
   on your bucket. AWS's guide: search "GitHub Actions OIDC AWS IAM role".
2. In your GitHub repo → **Settings → Secrets and variables → Actions**:
   - **Variables:** `USE_OIDC=true`, `AWS_REGION=ap-south-1`, `S3_BUCKET_NAME=geetha-portfolio-site`
   - **Secrets:** `AWS_DEPLOY_ROLE_ARN` = the role's ARN

### Simpler (but less secure): access keys
1. Create an IAM user with only `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`
   permission scoped to your bucket — never use your root or admin credentials here.
2. **Variables:** `USE_OIDC=false` (or leave unset), `AWS_REGION`, `S3_BUCKET_NAME`
3. **Secrets:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

Push again (or use **Actions → Deploy portfolio to S3 → Run workflow**) and
watch it deploy.

This whole setup — IaC template, Lambda function, and a CI/CD pipeline that
deploys on every push — is itself a legitimate project to describe in
interviews and list on your resume/LinkedIn.

---

## 6. Managing your AWS budget (you're on the paid plan)

Since you're on a **paid AWS account** rather than the free 6-month Free Plan,
nothing here is free by default except services that fall under AWS's
always-free tier allowances — so cost guardrails matter. Everything below is
in the AWS Console under **Billing and Cost Management**.

**Set up AWS Budgets (do this first, it takes 5 minutes):**
1. Console → Billing and Cost Management → **Budgets** → Create budget
2. Choose **Cost budget** → Monthly → set an amount you're comfortable with
   (even something like $5–10/month while learning)
3. Add an alert threshold, e.g. "notify me at 80% of budgeted amount" and
   "notify me if forecasted to exceed 100%"
4. Enter your email for notifications

Creating and monitoring cost budgets is free — AWS only charges for
*action-enabled* budgets (ones that auto-trigger a remediation, like stopping
an instance) beyond a small free allowance.

**A few other habits worth building as a DevOps engineer:**
- Turn on **Free Tier usage alerts** (Billing preferences) — AWS notifies you
  by email once you cross 85% of a free-tier limit on any service.
- Check **Cost Explorer** weekly while you're actively experimenting, to catch
  anything left running (a forgotten EC2 instance or NAT gateway is the most
  common surprise bill).
- Tag every resource you create (`Project=portfolio`) so costs are easy to
  trace back and clean up.
- Delete/stop resources from practice projects once you're done with them —
  S3 storage for this site is a few cents a month, but EC2, NAT gateways, and
  RDS instances keep billing while running.
- Consider setting up a second, stricter budget (e.g. $1) scoped to services
  you're not actively using, purely as a tripwire.

---

## 7. Posting this on LinkedIn

Once the site is live, a good post covers: what you built, what it
demonstrates technically, and a link. Ask me and I'll draft that for you as a
ready-to-post message.
