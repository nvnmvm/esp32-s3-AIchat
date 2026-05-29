# ESP32 AI Voice Cloud

Phase 1 cloud service for testing ESP32-S3 to VPS WebSocket communication.

The service exposes:

- `GET /health`
- `WebSocket /ws?token=YOUR_TOKEN&device_id=esp32-s3-voice-001`

It accepts text or binary frames, logs packet sizes, and echoes the same payload back to the ESP32.

## Local or VPS Deployment

```bash
cp .env.example .env
docker compose up -d --build
```

Or use the interactive deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` lets you choose:

- random WebSocket token
- custom WebSocket token

After deployment, copy the printed `WS_HOST`, `WS_PORT`, and `WS_TOKEN` into `../esp32-s3-firmware/include/config.h`.

## One-Line VPS Install From GitHub

Run this on a Debian or Ubuntu VPS:

```bash
curl -fsSL https://raw.githubusercontent.com/nvnmvm/esp32-s3-AIchat/main/install.sh -o install.sh
sudo bash install.sh --repo https://github.com/nvnmvm/esp32-s3-AIchat.git
```

The installer will:

- install Docker, Docker Compose, Git, Curl, and OpenSSL
- use the distro Docker packages first, then fall back to Docker's official apt repository if needed
- clone or update the project under `/opt/esp32-ai-voice-cloud`
- ask whether to generate a random WebSocket token or use a custom one
- create `.env`
- run `docker compose up -d --build`

## Publish This Folder To GitHub

With GitHub CLI installed and logged in:

```bash
cd esp32-ai-voice-cloud
git init
git add .
git commit -m "Initial ESP32 AI voice cloud service"
gh repo create nvnmvm/esp32-s3-AIchat --public --source . --remote origin --push
```

Without GitHub CLI, create an empty GitHub repo in the browser, then:

```bash
cd esp32-ai-voice-cloud
git init
git add .
git commit -m "Initial ESP32 AI voice cloud service"
git remote add origin https://github.com/nvnmvm/esp32-s3-AIchat.git
git push -u origin main
```

On Windows, after creating an empty GitHub repo in the browser:

```powershell
cd esp32-ai-voice-cloud
.\publish-to-github.ps1 -RepositoryUrl https://github.com/nvnmvm/esp32-s3-AIchat.git
```

## Logs

```bash
docker compose logs -f
```

Expected log flow:

- `ESP32 connected`
- `Received text ...`
- `Echoed text ...`
- `ESP32 disconnected`
