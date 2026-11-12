# QUANT ALGO - joining as a member

Every member gets a fully separate instance: own server, own fixed IP, own database, own Dhan account.
Nothing is shared: not market data, not keys, not positions, not history. The platform owner cannot see your
credentials or your trades, and nobody else's instance can reach yours.

## What you bring (all yours, entered only by you, never sent to anyone)
1. A Dhan account with the Trading API and a **Data API subscription in your own name** (you pay Dhan directly).
2. Your Dhan API key and secret.

## What the platform owner gives you
1. Your web address (for example `https://algoN.samirmishra.com`) and your server's fixed IP.
2. The Red Bar strategy file (sent to you directly, not published).

## If you already have your own VM (no server from the owner needed)
On a fresh Debian/Ubuntu VM you own, with ports 80 and 443 open and your web address already pointing at its public IP:
```bash
curl -fsSLO https://raw.githubusercontent.com/iitkgpsam/quant-algo/main/deploy/node/install-on-vm.sh
sudo QA_DOMAIN=algo.yourdomain.com bash install-on-vm.sh
```
It installs everything, gets your HTTPS certificate and prints your server's IP. Use that IP as your Dhan static IP.
Then follow the steps below from step 1. The VM, its IP and the bill stay yours.

## Your steps, in order
1. **Open `/setup` and create your admin password immediately.** Until you do, anyone who learns the address could claim it.
2. **Switch to Analyzer Mode** (lightning icon, top right) and confirm the badge says "Analyzer Mode".
   A new instance starts in Live Mode. Do this before anything else.
3. **Dhan settings** (web.dhan.co, API access): register your server's fixed IP as your static IP, and set the app's
   redirect URL to exactly `https://<your address>/dhan/callback`.
4. **Broker Configuration:** choose Dhan and save your key as `ClientID:::APIKey` (three colons, no spaces) with your secret.
5. **Login with Dhan** and approve with your PIN. The dashboard should open.
6. **Python Strategies -> Add Strategy:** upload the Red Bar file. Before uploading, open it and set:
   `INDEX` (NIFTY or SENSEX) and `ALLOCATION` (your own rupee amount; 0 means it will not run).
   Exchange: NFO for NIFTY, BFO for SENSEX. Schedule: Monday-Friday, 09:15 to 15:30.
7. Run in Analyzer Mode for at least one full session and read the log before deciding anything else.
   Going live is your own decision on your own instance and is not part of this onboarding.

## Approval and removal
The strategy file only runs with an **approval token** from the platform owner (the `LICENSE_TOKEN` line at the top).
The owner decides who is approved. A token expires (usually 30 days) and the owner can remove a member at any time: the
strategy then closes anything it has open, opens nothing new, and stops within about 10 minutes. Removal affects the
strategy file and the `samirmishra.com` web address only; your server, your Dhan account and your data stay yours.

## Rules that protect you
- Never paste your Dhan key, secret or token into a chat, email or form other than your own instance.
- Do not share your admin login.
- Paper results are optimistic: fills are instant and funds are virtual.

## For the platform owner: approving and removing (on your own server, qa1)
```bash
sudo apt-get install -y python3-cryptography
sudo python3 /opt/quant-algo/deploy/tools/qa_license.py init                       # once; prints your PUBLIC key
sudo python3 /opt/quant-algo/deploy/tools/qa_license.py issue --member alice --days 30   # APPROVE: prints alice's token
sudo python3 /opt/quant-algo/deploy/tools/qa_license.py revoke --member alice            # REMOVE
sudo python3 /opt/quant-algo/deploy/tools/qa_license.py list
```
Paste your public key into `LICENSE_PUBKEY` in the strategy file once, before you send it out. Honest limit: this controls the
strategy file you distribute; it cannot stop someone running the open-source platform on their own server, and a member who
edits their own copy of the file can remove the check.

## For the platform owner: adding a member
```bash
deploy/gcp/add-member.sh algoN.samirmishra.com     # creates the next instance, prints its fixed IP
```
Then add the DNS A record it prints, send the member their address, IP and the strategy file, and point them to this page.
Each instance costs roughly US$35-40 per month in the owner's Google Cloud billing (estimate, verify before billing).

## Updates
The platform code is shared; your instance changes only when you choose. To update yours (keeps your data and keys):
```bash
sudo QA_NAME=member QA_DOMAIN=algo.yourdomain.com bash /opt/quant-algo/deploy/node/update.sh
```
