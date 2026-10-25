#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl python3-yaml nginx
curl --fail --location --retry 5 'https://github.com/k3s-io/k3s/releases/download/v1.37.1%2Bk3s1/k3s' -o /usr/local/bin/k3s
echo '92b94582eb7b34a8cf532e6006842b9ed215a6783cf56a3dd6271fd35243b2c0  /usr/local/bin/k3s' | sha256sum --check
chmod 755 /usr/local/bin/k3s
mkdir -p /etc/rancher/k3s
cat > /etc/rancher/k3s/config.yaml <<'CONFIG'
write-kubeconfig-mode: "0600"
secrets-encryption: true
disable:
  - traefik
  - servicelb
CONFIG
curl --fail --location --retry 5 'https://raw.githubusercontent.com/k3s-io/k3s/356c025475bbefaa09cf0d7e48e8e2adbbde57db/install.sh' -o /opt/image-pipeline/install-k3s.sh
INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_EXEC=server sh /opt/image-pipeline/install-k3s.sh
for attempt in $(seq 1 60); do
  if k3s kubectl wait --for=condition=Ready nodes --all --timeout=10s; then break; fi
  sleep 5
done
k3s kubectl wait --for=condition=Ready nodes --all --timeout=120s
k3s kubectl apply -f /opt/image-pipeline/bootstrap.yaml
cat > /etc/nginx/sites-available/default <<'NGINX'
server {
  listen 80 default_server;
  server_name _;
  location / {
    proxy_pass http://127.0.0.1:30080;
    proxy_connect_timeout 3s;
    proxy_read_timeout 10s;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
NGINX
nginx -t
systemctl enable nginx
systemctl restart nginx
mkdir -p /var/lib/image-pipeline
touch /var/lib/image-pipeline/bootstrap-complete
