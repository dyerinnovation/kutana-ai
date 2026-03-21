# DGX Spark — Always-On Claude Code Workstation Setup Guide

> Complete setup guide for configuring an NVIDIA DGX Spark as a persistent AI development workstation with secure remote access via GL.iNet Flint 2 (GL-BE3600) WireGuard VPN.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      WireGuard VPN (10.0.0.0/24)            │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Personal Mac │    │   Mac Mini   │    │  iPhone/iPad │  │
│  │  (Client)     │    │  (Control    │    │  (Remote     │  │
│  │  SSH + Dispatch│   │   Plane)     │    │   Control)   │  │
│  │  10.0.0.3     │    │  10.0.0.4   │    │  10.0.0.5    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                    │                    │          │
│         └────────────┬───────┴────────────┬──────┘          │
│                      │                    │                  │
│              ┌───────┴────────┐   ┌───────┴────────┐       │
│              │  GL.iNet Flint │   │   DGX Spark    │       │
│              │  2 Router      │   │   (Workhorse)  │       │
│              │  WireGuard SVR │   │   Claude Code  │       │
│              │  192.168.8.1   │   │   Convene AI   │       │
│              │  DDNS enabled  │   │   Whisper GPU  │       │
│              └────────────────┘   │   10.0.0.2     │       │
│                                   └────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Network & VPN Setup (GL.iNet Flint 2)

### 1.1 Access the Router Admin Panel
```bash
# Default address (connect to the router's WiFi or LAN first)
open http://192.168.8.1
# Default password is on the bottom of the router
```

### 1.2 Assign DGX Spark a Static IP
1. Go to **Network → LAN → Static IP Address Binding**
2. Find the DGX Spark by MAC address
3. Assign it a fixed IP (e.g., `192.168.8.100`)
4. Save and apply

### 1.3 Enable WireGuard Server
1. Go to **VPN → WireGuard Server**
2. Click **Enable**
3. Set listening port: `51820` (default)
4. Server address will auto-configure (e.g., `10.0.0.1/24`)
5. Click **Apply**

### 1.4 Generate Client Configurations
1. Still in WireGuard Server, click **Add Client**
2. Create three profiles:
   - `mac-dev` — your personal Mac
   - `mac-mini` — control plane Mac Mini (if using)
   - `iphone` — mobile Remote Control access
3. Download each `.conf` file

### 1.5 Set Up Dynamic DNS (if ISP gives dynamic IP)
1. Go to **Applications → Dynamic DNS**
2. Enable **GoodCloud DDNS** (built-in, free)
   - Or use Cloudflare/DuckDNS/No-IP
3. Note your DDNS hostname (e.g., `yourname.glddns.com`)
4. Update the WireGuard client configs to use this hostname as the Endpoint

### 1.6 Port Forwarding (if GL.iNet is behind another router)
If the Flint 2 is behind an ISP modem/router:
1. Access the upstream router's admin panel
2. Forward UDP port `51820` to the Flint 2's WAN IP
3. Or put the Flint 2 in the upstream router's DMZ

### 1.7 Install WireGuard on Mac
```bash
# Install via Homebrew
brew install wireguard-tools

# Or install the WireGuard app from Mac App Store (has GUI)

# Import the config
sudo cp mac-dev.conf /etc/wireguard/wg0.conf

# Connect
sudo wg-quick up wg0

# Verify
sudo wg show
ping 10.0.0.1  # Should reach the router
ping 192.168.8.100  # Should reach the DGX Spark
```

### 1.8 Install WireGuard on iPhone
1. Install **WireGuard** from the App Store
2. Tap **+** → **Create from QR code** or **Import from file**
3. Import the `iphone.conf` profile
4. Toggle to connect

---

## Phase 2: DGX Spark Base Setup

### 2.1 Initial System Setup
```bash
# Connect via monitor/keyboard for initial setup, or SSH if already configured
# Update system
sudo apt update && sudo apt upgrade -y

# Set hostname
sudo hostnamectl set-hostname dgx-spark

# Install essential tools
sudo apt install -y curl git tmux htop ufw fail2ban
```

### 2.2 SSH Hardening
```bash
# On your Mac: copy SSH key to the DGX
ssh-copy-id user@192.168.8.100

# On the DGX: disable password auth
sudo sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Test key-based SSH works before closing this session!
```

### 2.3 Install Docker
```bash
# Docker (should be pre-installed on DGX, but if not):
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Docker Compose (v2, comes with Docker)
docker compose version
```

### 2.4 Install Node.js (for Claude Code)
```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
source ~/.bashrc

# Install latest LTS
nvm install --lts
nvm use --lts
node --version  # Should be 22.x+
```

### 2.5 Install Python 3.12+ and uv
```bash
# Python (should be pre-installed on DGX)
python3 --version

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

### 2.6 Install Bun (for Channel Server)
```bash
curl -fsSL https://bun.sh/install | bash
source ~/.bashrc
bun --version
```

### 2.7 Create Dedicated Claude User
```bash
# Create user with restricted shell
sudo adduser claude
sudo usermod -aG docker claude

# Create project directory
sudo mkdir -p /home/claude/projects
sudo chown claude:claude /home/claude/projects

# Copy SSH key for claude user too
sudo -u claude mkdir -p /home/claude/.ssh
sudo cp ~/.ssh/authorized_keys /home/claude/.ssh/
sudo chown -R claude:claude /home/claude/.ssh
sudo chmod 700 /home/claude/.ssh
sudo chmod 600 /home/claude/.ssh/authorized_keys
```

---

## Phase 3: Claude Code Setup

### 3.1 Install Claude Code
```bash
# As the claude user
sudo -u claude -i
npm install -g @anthropic-ai/claude-code
claude --version
```

### 3.2 Authenticate (Headless)
```bash
# From your Mac, create an SSH tunnel for the auth callback:
ssh -L 8080:localhost:8080 claude@192.168.8.100

# Then on the DGX (through that SSH session):
claude auth login
# Follow the browser URL — it will open on your Mac through the tunnel
```

### 3.3 Install Discord Channel Plugin
```bash
# Start Claude Code interactively first
claude

# Inside Claude Code:
/plugin marketplace add anthropics/claude-plugins-official
/plugin install discord@claude-plugins-official
/discord:configure <your-discord-bot-token>

# Test it works:
# Exit and restart with channels
claude --channels plugin:discord@claude-plugins-official
# Send a message to your Discord bot — should get a response
```

### 3.4 Set Up as Systemd Service
```bash
# Create environment file (as root)
sudo tee /home/claude/.env.claude << 'EOF'
ANTHROPIC_API_KEY=your-anthropic-key-here
NODE_ENV=production
EOF
sudo chown claude:claude /home/claude/.env.claude
sudo chmod 600 /home/claude/.env.claude

# Create systemd service
sudo tee /etc/systemd/system/claude-code.service << 'EOF'
[Unit]
Description=Claude Code with Discord Channel
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=claude
Group=claude
WorkingDirectory=/home/claude/projects/convene-ai
EnvironmentFile=/home/claude/.env.claude
ExecStart=/home/claude/.nvm/versions/node/v22.0.0/bin/claude --channels plugin:discord@claude-plugins-official --dangerously-skip-permissions
Restart=always
RestartSec=10

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/claude
PrivateTmp=true

# Resource limits
MemoryMax=4G
CPUQuota=200%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-code

[Install]
WantedBy=multi-user.target
EOF

# Fix the node path (find your actual path)
which claude  # as claude user
# Update ExecStart path in the service file accordingly

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable claude-code
sudo systemctl start claude-code

# Verify
sudo systemctl status claude-code
journalctl -u claude-code -f  # Watch logs
```

---

## Phase 4: Convene AI Stack

### 4.1 Clone and Configure
```bash
sudo -u claude -i
cd ~/projects
git clone <your-repo-url> convene-ai
cd convene-ai

# Copy environment file
cp .env.example .env
# Edit .env with your actual keys:
#   DEEPGRAM_API_KEY=your-key
#   ANTHROPIC_API_KEY=your-key
#   DATABASE_URL=postgresql+asyncpg://convene:convene@postgres:5432/convene
#   REDIS_URL=redis://redis:6379
nano .env
```

### 4.2 Start the Stack
```bash
docker compose up -d

# Watch logs
docker compose logs -f

# Check all services are healthy
docker compose ps
```

### 4.3 Verify Pipeline
```bash
# Run the pipeline test
cd examples
python3 test-pipeline.py

# Should see:
# ✅ User registered
# ✅ Meeting created
# ✅ Transcript segments published
# ✅ Entities extracted
# ✅ Pipeline test PASSED
```

---

## Phase 5: Self-Hosted Whisper (Optional — Uses GPU)

### 5.1 Install NVIDIA Container Toolkit
```bash
# Should be pre-installed on DGX Spark, but if not:
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 5.2 Run Faster-Whisper Server
```bash
# Docker with GPU (recommended)
docker run -d \
  --name whisper-server \
  --gpus all \
  -p 8080:8080 \
  -e WHISPER__MODEL=large-v3 \
  -e WHISPER__DEVICE=cuda \
  fedirz/faster-whisper-server:latest

# Verify
curl http://localhost:8080/health

# Test transcription
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -F "file=@test-audio.wav" \
  -F "model=large-v3"
```

### 5.3 Configure in Convene AI
```bash
# Add to .env:
echo 'CONVENE_STT_PROVIDER=whisper-local' >> ~/projects/convene-ai/.env
echo 'WHISPER_SERVER_URL=http://host.docker.internal:8080' >> ~/projects/convene-ai/.env

# Restart audio service to pick up the change
cd ~/projects/convene-ai
docker compose restart audio-service
```

---

## Phase 6: Security Hardening

### 6.1 Firewall (UFW)
```bash
# Reset and configure
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH only from local network and VPN
sudo ufw allow from 192.168.8.0/24 to any port 22    # LAN
sudo ufw allow from 10.0.0.0/24 to any port 22       # VPN

# Allow Convene AI ports only from VPN/LAN
sudo ufw allow from 192.168.8.0/24 to any port 8000:8003 proto tcp
sudo ufw allow from 10.0.0.0/24 to any port 8000:8003 proto tcp

# Allow Whisper server from local only
sudo ufw allow from 192.168.8.0/24 to any port 8080 proto tcp

# Enable
sudo ufw enable
sudo ufw status verbose
```

### 6.2 Fail2Ban for SSH
```bash
sudo tee /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
EOF

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban
```

### 6.3 API Key Management
```bash
# Ensure .env is readable only by claude user
chmod 600 /home/claude/projects/convene-ai/.env
chmod 600 /home/claude/.env.claude

# Set spending limits:
# - Anthropic: console.anthropic.com → Settings → Spending Limits
# - Deepgram: console.deepgram.com → Settings → Usage Limits
```

### 6.4 Automatic Security Updates
```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes" to enable automatic updates
```

---

## Phase 7: Monitoring & Maintenance

### 7.1 Health Check Script
```bash
sudo tee /home/claude/health-check.sh << 'SCRIPT'
#!/bin/bash
DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
HOSTNAME=$(hostname)
ERRORS=""

# Check Claude Code service
if ! systemctl is-active --quiet claude-code; then
    ERRORS+="❌ Claude Code service is DOWN\n"
fi

# Check Docker containers
cd /home/claude/projects/convene-ai
UNHEALTHY=$(docker compose ps --format json 2>/dev/null | jq -r 'select(.Health != "healthy" and .State != "running") | .Service' 2>/dev/null)
if [ -n "$UNHEALTHY" ]; then
    ERRORS+="❌ Unhealthy containers: $UNHEALTHY\n"
fi

# Check disk space (alert if >85%)
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 85 ]; then
    ERRORS+="⚠️ Disk usage at ${DISK_PCT}%\n"
fi

# Check GPU
if ! nvidia-smi > /dev/null 2>&1; then
    ERRORS+="❌ GPU not responding\n"
fi

# Send alert if issues found
if [ -n "$ERRORS" ]; then
    curl -s -H "Content-Type: application/json" \
         -d "{\"content\":\"🚨 **$HOSTNAME Health Alert**\n$ERRORS\"}" \
         "$DISCORD_WEBHOOK"
fi
SCRIPT

chmod +x /home/claude/health-check.sh

# Run every 5 minutes
(crontab -l 2>/dev/null; echo "*/5 * * * * /home/claude/health-check.sh") | crontab -
```

### 7.2 Automated Backups
```bash
sudo tee /home/claude/backup.sh << 'SCRIPT'
#!/bin/bash
BACKUP_DIR="/home/claude/backups"
DATE=$(date +%Y%m%d)
mkdir -p "$BACKUP_DIR"

# Backup configs and keys
tar czf "$BACKUP_DIR/config-$DATE.tar.gz" \
    /home/claude/.env.claude \
    /home/claude/projects/convene-ai/.env \
    /home/claude/projects/convene-ai/docker-compose.yml

# Backup PostgreSQL
docker exec convene-ai-postgres-1 pg_dump -U convene convene | \
    gzip > "$BACKUP_DIR/db-$DATE.sql.gz"

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete
SCRIPT

chmod +x /home/claude/backup.sh

# Run daily at 2 AM
(crontab -l 2>/dev/null; echo "0 2 * * * /home/claude/backup.sh") | crontab -
```

### 7.3 Log Monitoring
```bash
# View Claude Code logs
journalctl -u claude-code -f

# View all Convene AI logs
cd ~/projects/convene-ai && docker compose logs -f

# View specific service
docker compose logs -f api-server
docker compose logs -f task-engine
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Start VPN (Mac) | `sudo wg-quick up wg0` |
| Stop VPN (Mac) | `sudo wg-quick down wg0` |
| SSH to DGX | `ssh claude@192.168.8.100` |
| Claude Code logs | `journalctl -u claude-code -f` |
| Restart Claude Code | `sudo systemctl restart claude-code` |
| Start Convene AI | `cd ~/projects/convene-ai && docker compose up -d` |
| Stop Convene AI | `cd ~/projects/convene-ai && docker compose down` |
| View all containers | `docker compose ps` |
| View container logs | `docker compose logs -f <service>` |
| Check GPU | `nvidia-smi` |
| Check disk | `df -h` |
| Run pipeline test | `cd ~/projects/convene-ai/examples && python3 test-pipeline.py` |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| VPN won't connect | Check port 51820/UDP is forwarded, verify DDNS resolves |
| Claude Code won't start | Check `journalctl -u claude-code -e`, verify API key in .env.claude |
| Discord bot not responding | Restart service: `sudo systemctl restart claude-code` |
| Docker containers crash | Check logs: `docker compose logs <service>`, verify .env keys |
| GPU not detected | Run `nvidia-smi`, check NVIDIA Container Toolkit installed |
| Out of disk space | `docker system prune -a` to clean unused images |
| SSH connection refused | Check UFW rules: `sudo ufw status`, ensure VPN is connected |
