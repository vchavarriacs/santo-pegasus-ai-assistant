#!/bin/bash
# Provisioning script para OCI VM (Ubuntu 22.04 ARM Ampere)

set -e

echo "=== Instalando Docker ==="
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER

echo "=== Instalando Cloudflare Tunnel ==="
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
sudo dpkg -i cloudflared.deb
rm cloudflared.deb

echo "=== Clonando repositorio ==="
git clone https://github.com/YOUR_USER/santo-pegasus-ai-assistant.git
cd santo-pegasus-ai-assistant

echo "=== Configurando variables de entorno ==="
cp .env.example .env
echo "EDITA el archivo .env con tus credenciales antes de continuar."
echo "  nano .env"

echo "=== Listo. Ejecuta: ==="
echo "  cd santo-pegasus-ai-assistant"
echo "  docker compose up -d"
echo "  cloudflared tunnel --url http://localhost:5678"
