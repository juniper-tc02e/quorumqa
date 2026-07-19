# Deploying QuorumQA's backend on Alibaba Cloud

The hackathon rules require the backend to actually **run on** Alibaba
Cloud, with a linked code file proving real Alibaba Cloud API usage (not
just a hosting location). This directory covers both halves: where the
backend runs (ECS), and what Alibaba Cloud service it genuinely calls
(`oss_client.py`, using OSS to persist every deliberation transcript).

ECS was chosen over Function Compute deliberately: a contested question can
take several sequential LLM calls (solvers -> skeptic -> verifier -> judge),
which is a poor fit for FC's request/response timeout model under a tight
build schedule. A small always-on VM is the least surprising option with
four days on the clock.

## 1. Create the ECS instance

1. Alibaba Cloud Console -> ECS -> Create Instance.
2. Cheapest burstable instance type available on your account (e.g. an
   `ecs.t6`/`ecs.e` series, 2 vCPU / 4GB is plenty for this workload --
   it's I/O-bound on the Qwen Cloud API, not compute-bound).
3. Image: Ubuntu 22.04 LTS.
4. Security group: open port 22 (SSH, restrict to your IP) and port 8501
   (Streamlit dashboard) and/or 8000 (FastAPI, if you add an API layer).
5. Note the public IP once it's running.

## 2. Provision the instance

```bash
ssh root@<ECS_PUBLIC_IP>
apt-get update && apt-get install -y python3.11 python3.11-venv git
git clone <your-repo-url> quorumqa && cd quorumqa
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e . -r requirements.txt
cp .env.example .env  # fill in DASHSCOPE_API_KEY, OSS_* vars
```

## 3. Run as a systemd service (so it survives disconnects/reboots)

`/etc/systemd/system/quorumqa-dashboard.service`:

```ini
[Unit]
Description=QuorumQA Streamlit dashboard
After=network.target

[Service]
WorkingDirectory=/root/quorumqa
EnvironmentFile=/root/quorumqa/.env
ExecStart=/root/quorumqa/.venv/bin/streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now quorumqa-dashboard
```

Dashboard is now live at `http://<ECS_PUBLIC_IP>:8501`.

## 4. Create the OSS bucket (for the proof-of-deployment artifact)

1. Console -> Object Storage Service -> Create Bucket, name it e.g.
   `quorumqa-transcripts`, same region as the ECS instance. Leave ACL =
   Private and Block Public Access on.
2. RAM console -> Identities -> Users -> Create User. Check "Using
   permanent AccessKey to access" -- don't use root account keys. Copy the
   AccessKey ID/Secret from the one-time dialog immediately; the secret
   cannot be retrieved again once it closes.
3. Attach a policy scoped to just this bucket (NOT `AliyunOSSFullAccess`,
   which grants every bucket in the account, not just this one):
   ```json
   {
     "Version": "1",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["oss:GetObject", "oss:PutObject", "oss:ListObjects", "oss:DeleteObject"],
       "Resource": ["acs:oss:*:*:quorumqa-transcripts", "acs:oss:*:*:quorumqa-transcripts/*"]
     }]
   }
   ```
   RAM console -> user -> Permissions tab -> Grant Permission -> Create
   Policy (paste the JSON above, swapping in your real bucket name) ->
   attach it to the user.
4. Put the RAM user's `AccessKeyId`/`AccessKeySecret` into `.env` as
   `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET`.
5. Run a smoke test from the ECS instance:
   `python -c "from deploy.oss_client import upload_run_summary; print(upload_run_summary('test', 'smoke-test'))"`
   -- a successful key print is your proof the deployed code is genuinely
   calling Alibaba Cloud's API, not just running near it.

## Submission checklist for this section

- [ ] Linked code file: `deploy/oss_client.py` (real OSS SDK usage).
- [ ] Repo README states the ECS public IP / demo URL, or a short clip in
      the demo video showing `systemctl status quorumqa-dashboard` on the
      actual instance.
- [ ] `.env` (with real keys) is **not** committed -- verify `.gitignore`
      covers it before pushing.
