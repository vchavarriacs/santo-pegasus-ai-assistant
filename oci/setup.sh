#!/bin/bash
# Provisioning script para OCI VM Always Free (Oracle Linux 9, ARM Ampere)
#
# Probado sobre una instancia real: Oracle Linux 9.7, aarch64, VM.Standard.A1.Flex.
# Si tu imagen es Ubuntu en lugar de Oracle Linux, cambia dnf por apt siguiendo
# la documentación oficial de Docker (https://docs.docker.com/engine/install/ubuntu/).

set -e

echo "=== Instalando Docker ==="
sudo dnf install -y dnf-utils git
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
echo "Cierra sesión y vuelve a entrar (o 'newgrp docker') para usar Docker sin sudo."

echo "=== Instalando Cloudflare Tunnel (repo oficial) ==="
sudo tee /etc/yum.repos.d/cloudflared.repo <<'EOF'
[cloudflared-stable]
name=cloudflared-stable
baseurl=https://pkg.cloudflare.com/cloudflared/rpm
gpgcheck=1
enabled=1
gpgkey=https://pkg.cloudflare.com/cloudflare-main.gpg
EOF
sudo dnf install -y cloudflared

echo "=== Clonando repositorio ==="
git clone https://github.com/YOUR_USER/santo-pegasus-ai-assistant.git
cd santo-pegasus-ai-assistant

echo "=== Configurando variables de entorno ==="
cp .env.example .env
echo "EDITA el archivo .env con tus credenciales antes de continuar (sin comillas, sin espacios alrededor del '='):"
echo "  nano .env"

cat <<'EOF'

=== Pasos siguientes (manuales) ===

1. Levantar Qdrant e indexar los PDFs:
     docker compose up -d qdrant
     pip3 install --user pdfplumber requests
     export COHERE_API_KEY=$(grep COHERE_API_KEY .env | cut -d '=' -f2)
     python3 scripts/ingest.py

2. Crear un tunnel de Cloudflare DEDICADO para esta VM (no reutilices el token
   de otro entorno n8n — cada tunnel debe apuntar a un solo backend):
     cloudflared tunnel login
     cloudflared tunnel create santo-pegasus-oci
     cloudflared tunnel route dns santo-pegasus-oci tu-subdominio.tu-dominio.com

3. Configurar el tunnel como servicio systemd (persiste tras reinicios):
     sudo mkdir -p /etc/cloudflared
     sudo tee /etc/cloudflared/config.yml <<CFG
tunnel: <TUNNEL_ID>
credentials-file: /home/$USER/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: tu-subdominio.tu-dominio.com
    service: http://localhost:5678
  - service: http_status:404
CFG
     sudo cp ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/
     sudo cloudflared service install
     sudo systemctl enable --now cloudflared

4. Levantar n8n y actualizar N8N_HOST/WEBHOOK_URL en .env con tu subdominio,
   luego:
     docker compose up -d n8n

5. Importar n8n/workflow.json en la UI de n8n, asignar credenciales
   (Cohere, Gemini, Qdrant) y probar el chat.

EOF
