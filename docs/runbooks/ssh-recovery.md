# SSH recovery for Contabo VPS

Use this guide from the VNC/KVM console to restore SSH access for [`66.94.101.153`](terraform/terraform.tfvars) and align it with the key already configured in [`terraform.tfvars`](terraform/terraform.tfvars).

## Target key

This is the public key that Terraform already expects for [`deploy`](terraform/variables.tf):

```text
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOoaw6hhxR/+qcz1OLPnGHqJdFEvw/iTlGHKJnSOI4JX vps_rt_infra-deploy
```

## 1) Log in as root in the VNC console

After you reach the shell, run:

```bash
whoami
hostname
ip a | sed -n '1,120p'
```

You should be `root` on the VPS.

## 2) Create or repair the `deploy` user

```bash
id deploy || useradd -m -s /bin/bash deploy
usermod -aG sudo deploy
usermod -aG docker deploy 2>/dev/null || true
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
```

## 3) Install the correct SSH key for both `deploy` and `root`

```bash
cat > /home/deploy/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOoaw6hhxR/+qcz1OLPnGHqJdFEvw/iTlGHKJnSOI4JX vps_rt_infra-deploy
EOF
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

mkdir -p /root/.ssh
chmod 700 /root/.ssh
cat > /root/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOoaw6hhxR/+qcz1OLPnGHqJdFEvw/iTlGHKJnSOI4JX vps_rt_infra-deploy
EOF
chmod 600 /root/.ssh/authorized_keys
```

## 4) Ensure sudo works for `deploy`

```bash
cat > /etc/sudoers.d/90-deploy <<'EOF'
deploy ALL=(ALL) NOPASSWD:ALL
EOF
chmod 440 /etc/sudoers.d/90-deploy
visudo -cf /etc/sudoers.d/90-deploy
```

## 5) Repair SSH daemon configuration

Open [`/etc/ssh/sshd_config`](../../../../etc/ssh/sshd_config) with:

```bash
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%F-%H%M%S)
nano /etc/ssh/sshd_config
```

Make sure these effective settings exist exactly once:

```text
PubkeyAuthentication yes
PasswordAuthentication yes
PermitRootLogin yes
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
UsePAM yes
AuthorizedKeysFile .ssh/authorized_keys
```

Then validate and restart SSH:

```bash
sshd -t && systemctl restart ssh
systemctl status ssh --no-pager
```

## 6) If `fail2ban` is blocking your IP, clear the SSH jail

```bash
systemctl status fail2ban --no-pager || true
fail2ban-client status sshd || true
fail2ban-client set sshd unbanip YOUR_WINDOWS_PUBLIC_IP || true
systemctl restart fail2ban || true
```

If you do not know your public IP from the VPS shell:

```bash
curl -4 ifconfig.me
```

## 7) Verify locally on the VPS before leaving VNC

```bash
su - deploy -c 'whoami'
ls -la /home/deploy/.ssh
cat /home/deploy/.ssh/authorized_keys
sshd -T | egrep 'pubkeyauthentication|passwordauthentication|permitrootlogin|authorizedkeysfile'
```

## 8) Verify from Windows

Run these commands on Windows from [`c:/Users/lucas.rangel/Desktop/claude`](../ssh_debug_out.txt), using the current key `vps_rt_infra_ed25519_v2` (installed on the server via the Contabo "Reset credentials -> SSH Key" panel action):

### Verify deploy key auth

```cmd
ssh -i C:\Users\lucas.rangel\.ssh\vps_rt_infra_ed25519_v2 -o StrictHostKeyChecking=no deploy@66.94.101.153 "whoami && id"
```

Expected output should include:

```text
deploy
uid=1001(deploy) gid=1001(deploy) groups=1001(deploy),27(sudo),988(docker)
```

### Verify root key auth

```cmd
ssh -i C:\Users\lucas.rangel\.ssh\vps_rt_infra_ed25519_v2 -o StrictHostKeyChecking=no root@66.94.101.153 "whoami"
```

### Root password auth is disabled

Contabo's credential reset flow installs the SSH key into `/root/.ssh/authorized_keys` and disables root password authentication as a side effect. The old root password stored in [`secrets/contabo-vps.json`](../../secrets/contabo-vps.json) no longer works and should be treated as stale/informational only.

## 9) Status: SSH access recovered and deploy user provisioned

This recovery has been completed:

- The v2 SSH key (`vps_rt_infra_ed25519_v2`) is authorized for `root` on the server.
- [`cloud-init/bootstrap.sh`](cloud-init/bootstrap.sh) was executed manually over SSH (piped via stdin to `root@<host>`) to create the `deploy` user, since Terraform was not runnable locally. `deploy` now exists with `sudo` + `docker` group membership.
- [`terraform/main.tf`](terraform/main.tf) was updated so `null_resource.bootstrap` connects as `root` using `private_key = file(var.ssh_private_key_path)` (not password), since root password auth no longer works. `null_resource.deploy_stack` remains on `deploy_user` + the same private key.
- [`terraform/terraform.tfvars`](terraform/terraform.tfvars) and [`terraform/variables.tf`](terraform/variables.tf) now default `ssh_private_key_path` / `public_ssh_key` to the v2 key pair.

Remaining follow-up: re-run [`scripts/bootstrap_github_secrets.py`](scripts/bootstrap_github_secrets.py) (now pointed at the v2 key files) to push corrected `VPS_SSH_PRIVATE_KEY` / `VPS_PUBLIC_SSH_KEY` GitHub Actions secrets, then re-trigger the GitHub Actions apply pipeline to validate end-to-end.

## 10) Minimal one-shot recovery block

If you want a single paste block in VNC, use this:

```bash
id deploy || useradd -m -s /bin/bash deploy
usermod -aG sudo deploy
usermod -aG docker deploy 2>/dev/null || true
mkdir -p /home/deploy/.ssh /root/.ssh
chmod 700 /home/deploy/.ssh /root/.ssh
cat > /home/deploy/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOoaw6hhxR/+qcz1OLPnGHqJdFEvw/iTlGHKJnSOI4JX vps_rt_infra-deploy
EOF
cat > /root/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOoaw6hhxR/+qcz1OLPnGHqJdFEvw/iTlGHKJnSOI4JX vps_rt_infra-deploy
EOF
chmod 600 /home/deploy/.ssh/authorized_keys /root/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
cat > /etc/sudoers.d/90-deploy <<'EOF'
deploy ALL=(ALL) NOPASSWD:ALL
EOF
chmod 440 /etc/sudoers.d/90-deploy
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak.$(date +%F-%H%M%S)
sed -i 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config || echo 'PubkeyAuthentication yes' >> /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config || echo 'PasswordAuthentication yes' >> /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config || echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config
sed -i 's/^#\?KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' /etc/ssh/sshd_config || echo 'KbdInteractiveAuthentication no' >> /etc/ssh/sshd_config
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config || echo 'ChallengeResponseAuthentication no' >> /etc/ssh/sshd_config
sshd -t && systemctl restart ssh
systemctl restart fail2ban || true
```
