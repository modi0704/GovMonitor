# GovMonitor — Administrator guide

This guide is for the person who installs and runs GovMonitor: an agency's IT officer for an
office install, or the operator of the cloud service. It assumes no knowledge of the code.

Contents: [1 What you install](#1-what-you-install) · [2 Hardware](#2-hardware-sizing) ·
[3 Install on Linux](#3-install-on-linux) · [4 Install on Windows Server](#4-install-on-windows-server) ·
[5 First sign-in](#5-first-sign-in) · [6 Certificates and addresses](#6-certificates-and-addresses) ·
[7 Field offices, network and VPN](#7-field-offices-network-and-vpn) · [8 Email](#8-email-smtp) ·
[9 Backups](#9-backups-and-restore) · [10 Updates](#10-updates) · [11 Licence](#11-licence-office-installs) ·
[12 Cloud service](#12-cloud-service) · [13 Troubleshooting](#13-troubleshooting) ·
[14 Settings reference](#14-settings-reference)

---

## 1. What you install

GovMonitor runs as four containers on one machine, started with Docker Compose:

| Container | What it does |
|---|---|
| `db` | PostgreSQL 18: every plan, report, result and the audit log. |
| `web` | The application (web pages and API). Applies database updates when it starts. |
| `worker` | Background work: Excel and PowerPoint exports, plan imports, daily alerts, automatic locking. |
| `caddy` | The front door: HTTPS, compression, upload size limit. The only container reachable from the network. |

Data lives in Docker volumes: `pgdata` (database), `files` (supporting files, exports, logos) and
`caddy_data` (certificates). Back up the first two (section 9).

Nothing in GovMonitor needs the internet while it runs: no fonts, scripts or services are loaded
from outside. Email (optional) is the only outgoing connection.

## 2. Hardware sizing

| Size of the agency | CPU | Memory | Disk |
|---|---|---|---|
| Up to 100 offices, 200 users | 2 cores | 4 GB | 40 GB SSD |
| Up to 500 offices, 1,000 users, 5,000 activities a year (the tested ceiling) | 4 cores | 8 GB | 100 GB SSD |
| Cloud service, 50 agencies at that size | 8 cores for `web` + `worker`; managed PostgreSQL with 4 cores / 16 GB | — | storage grows with uploaded files |

Supporting files are the main growth: count about 2 MB per reported activity per month if offices
attach photos. Keep backups on a different disk or machine.

At the tested ceiling the dashboard answers in under 2 seconds, locking a month takes well under a
minute and a 500-activity office exports to Excel in about a second.

## 3. Install on Linux

Ubuntu Server 24.04 LTS (or any 64-bit Linux with Docker 24+).

1. Install Docker with its compose plugin (needs internet once, or your distribution's offline
   packages): `sudo apt install docker.io docker-compose-v2`.
2. Copy the offline bundle `govmonitor-offline-<version>.tar.gz` to the server and unpack it:

   ```bash
   tar -xzf govmonitor-offline-1.0.0.tar.gz
   cd govmonitor-offline-1.0.0
   sudo ./install.sh /opt/govmonitor
   ```

   The first run loads the images, creates `/opt/govmonitor/.env` with new random passwords and
   starts everything.
3. Edit `/opt/govmonitor/.env` for this server (section 6): `SITE_ADDRESS`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`, `PUBLIC_URL`, and email if wanted (section 8).
4. Put the licence file from the vendor at `/opt/govmonitor/licence/licence.json` (section 11).
5. Apply the changes: `cd /opt/govmonitor && sudo docker compose --env-file .env up -d`.
6. Open the firewall for ports 80 and 443 only (`sudo ufw allow 80,443/tcp`).

The containers restart by themselves after a reboot.

## 4. Install on Windows Server

Windows Server 2022 or later, with a Linux container runtime.

1. Install **Docker Desktop** (with WSL 2), or on Windows Server use Docker Engine with WSL 2 /
   Mirantis Container Runtime configured for **Linux containers**. Check with `docker version`
   that the server OS/Arch reads `linux/amd64`.
2. Unpack the bundle (7-Zip opens `.tar.gz`) into `C:\GovMonitor\bundle`.
3. Open "Ubuntu" (WSL) or Git Bash as administrator and run the installer with a Windows path:

   ```bash
   cd /mnt/c/GovMonitor/bundle/govmonitor-offline-1.0.0
   ./install.sh /mnt/c/GovMonitor/app
   ```

4. Continue with steps 3–5 of the Linux install, editing `C:\GovMonitor\app\.env` with Notepad.
5. Windows Firewall: allow inbound TCP 80 and 443.
6. Make Docker start at boot (Docker Desktop: "Start when you sign in", or run it as a service).

## 5. First sign-in

Create your agency and its first administrator (single-agency installs):

```bash
cd /opt/govmonitor
sudo docker compose --env-file .env exec web entrypoint.sh manage bootstrap_single_agency \
  --name "Department of Example" --code dept-example --admin-email chief@example.gov \
  --root-level-name Department
```

It prints a temporary password, shown once. Sign in at `https://<SITE_ADDRESS>/` with that email
and password, choose a new password, and the setup wizard walks through levels, offices, users and
the first fiscal year. The **Help** page in the application explains each role's work.

## 6. Certificates and addresses

Set these in `.env` and run `docker compose --env-file .env up -d` after any change.

| Situation | `SITE_ADDRESS` | `TLS_MODE` | Notes |
|---|---|---|---|
| Office network, no public name (most office installs) | `https://192.168.1.10` or `https://monitor.agency.local` | `internal` | Caddy makes its own certificate authority. Install its root certificate on staff computers once to avoid browser warnings: `docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./govmonitor-root.crt`, then distribute by group policy. |
| Your own certificate (agency PKI) | `https://monitor.agency.gov.ph` | `/certs/cert.pem /certs/key.pem` | Put both files in `certs/` next to `.env`. |
| Public name reachable from the internet | `monitor.example.gov` | *(empty)* | Automatic certificate from Let's Encrypt; needs ports 80/443 open to the internet. |
| Behind your own proxy or only over a VPN | `http://:80` | — | Also set `SECURE_SSL=0`. |

Always list every name and address people use in `ALLOWED_HOSTS` (comma separated, plus
`localhost`) and in `CSRF_TRUSTED_ORIGINS` (with `https://`), and set `PUBLIC_URL` to the main
address (used in email links).

## 7. Field offices, network and VPN

* Field offices reach the server over the agency WAN or a site-to-site VPN (WireGuard, IPsec or
  OpenVPN). Do not expose the server to the internet unless it has a public name and certificate.
* Pages are light: about 100 KB (compressed) on first load, then a few tens of KB per screen;
  a 1 Mbps link is enough.
  Supporting files are limited to 25 MB each (`MAX_UPLOAD_MB`); the proxy refuses larger requests.
* Staff with phones can follow dashboards and attach photos to an activity; editing screens
  (plans, monthly grid, structure, users) ask for a computer.
* Sessions end after 60 minutes without use (`SESSION_IDLE_MINUTES`).

## 8. Email (SMTP)

Email is optional. Without it, reminders and alerts still appear in the application (the bell).

```dotenv
EMAIL_URL=smtp://alerts%40agency.gov:app-password@smtp.agency.gov:587?tls=1&from=alerts@agency.gov
PUBLIC_URL=https://monitor.agency.gov
```

Use `?tls=1` (or the scheme `submission://`) for STARTTLS on port 587, `smtps://` for port 465, or
plain `smtp://` on port 25 inside the agency network; URL-encode `@` in the user name as `%40` and
set the sender with `from=`. Then, in the application, the agency administrator turns on **Alerts → Also send a
daily email digest**. Each person gets at most one short email a day and can turn it off on their
account page. Password-reset emails use the same server.

## 9. Backups and restore

`backup.sh` saves the database and all stored files into one dated archive and keeps the newest 14:

```bash
cd /opt/govmonitor
sudo BACKUP_DIR=/mnt/backup/govmonitor KEEP=30 ./backup.sh
```

Schedule it every night (Linux: `sudo crontab -e`):

```cron
30 1 * * * cd /opt/govmonitor && BACKUP_DIR=/mnt/backup/govmonitor ./backup.sh >> /var/log/govmonitor-backup.log 2>&1
```

On Windows use Task Scheduler with `wsl -d Ubuntu -- bash -c "cd /mnt/c/GovMonitor/app && ./backup.sh"`.
Copy the archives to another machine or offline media; a backup on the same disk does not protect
against disk failure.

**Restore** (same machine, or a new one where `install.sh` has run once):

```bash
cd /opt/govmonitor
sudo ./restore.sh /mnt/backup/govmonitor/govmonitor-20270101-013000.tar
```

It checks the archive, replaces all data, starts the system and waits until it is healthy. Every
build is tested by backing up, wiping the machine, restoring and comparing every frozen result.

## 10. Updates

Updates come as a new offline bundle. Unpack it anywhere and run its `update.sh`:

```bash
tar -xzf govmonitor-offline-1.1.0.tar.gz
cd govmonitor-offline-1.1.0
sudo ./update.sh /opt/govmonitor
```

It backs up first, loads the new images, starts them (the database is updated automatically) and
checks that the system is healthy. If anything fails, it **rolls back by itself** to the previous
version and the data from before the update, and says so. Your `.env`, certificates and licence
are kept. Expect a few minutes of downtime; run updates outside office hours.

## 11. Licence (office installs)

Single-agency installs need the licence file from the vendor at `licence/licence.json`. The
application shows a banner 30 days before it expires. Without a valid licence the system turns
**read-only**: everyone can still sign in, read everything and export it, but nothing can be
changed. The seat limit counts active users; above it no new user can be added (deactivate a user
or extend the licence). Replace the file and the change applies within a minute — no restart needed.
Cloud (multi-agency) installs do not use licences.

## 12. Cloud service

`docker-compose.cloud.yml` runs only `web` and `worker`; the database is a managed PostgreSQL 16+
and files go to S3-compatible storage. TLS ends at your load balancer.

1. Create the database and its two roles once with `deploy/db/init-roles.sh` (see its header).
   `app_owner` owns the tables and runs migrations; `app_user` is what the application uses and is
   bound by row-level security, so one agency can never read another's rows.
2. Create a private bucket and an access key limited to it.
3. Copy `cloud.env.example` to `cloud.env`, fill it in, and start:
   `docker compose -f docker-compose.cloud.yml --env-file cloud.env up -d`.
4. Platform owners (your staff) are created with
   `docker compose ... exec web entrypoint.sh manage create_platform_admin --email ops@vendor.example`;
   they create agencies at `/platform`.
5. Back up with your provider's database snapshots plus bucket versioning or replication.

## 13. Troubleshooting

| Symptom | What to check |
|---|---|
| Browser says "not secure" | Internal certificates: install Caddy's root certificate on the computers (section 6). |
| "Bad Request (400)" on every page | The address used is missing from `ALLOWED_HOSTS`. |
| "CSRF verification failed" when signing in | The address (with `https://`) is missing from `CSRF_TRUSTED_ORIGINS`. |
| Exports stay "Waiting" | The worker: `docker compose logs worker`. `https://<site>/api/v1/health` shows `"worker": {"ok": false}` when it has stopped. |
| No emails | `EMAIL_URL`, the Alerts page switch, and the person's own opt-out. Look for "digest" in `docker compose logs worker`. |
| "The licence ... read-only" banner | Section 11. |
| Upload refused as too large | `MAX_UPLOAD_MB` (application) and `MAX_BODY_MB` (proxy, keep it a few MB larger). |
| Site does not start after a reboot | `docker compose ps`; start Docker; `docker compose --env-file .env up -d`. |
| Disk full | `docker system df`; remove old backups and old images (`docker image prune`). |

Health at a glance: `curl -k https://<site>/api/v1/health` returns database, storage and worker
status. Logs: `docker compose logs --tail 200 web worker` (one JSON object per line).

## 14. Settings reference

| Setting | Default | Meaning |
|---|---|---|
| `DEPLOYMENT_MODE` | `single` (office) / `multi` (cloud) | One agency, or many with platform owners. |
| `SECRET_KEY` | generated | Signs sessions. Keep secret; changing it signs everyone out. |
| `SITE_ADDRESS`, `TLS_MODE` | `localhost`, `internal` | Section 6. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_URL` | localhost | Section 6. |
| `SECURE_SSL` | `1` | Cookies only over HTTPS and HSTS. Set `0` only for plain HTTP. |
| `EMAIL_URL` | empty | Section 8. |
| `MAX_UPLOAD_MB` / `MAX_BODY_MB` | 25 / 30 | Largest supporting file / largest request at the proxy. |
| `SESSION_IDLE_MINUTES` | 60 | Sign-out after inactivity. |
| `LICENCE_FILE` | `/licence/licence.json` | Section 11. |
| `LOG_FORMAT` | `json` | `plain` for reading logs by eye. |
| `HTTP_PORT`, `HTTPS_PORT`, `WEB_PORT` | 80, 443, 8000 | Ports on the host (`WEB_PORT` is reachable from the host only). |
| `POSTGRES_PASSWORD`, `APP_OWNER_PASSWORD`, `APP_USER_PASSWORD` | generated | Database passwords; set before the first start. |
