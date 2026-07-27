# Contabo delivers the VPS already provisioned (bought manually through the customer
# panel), so this module does not create a compute instance. Instead it treats the
# existing server as a target and:
#   1. bootstraps the OS (docker, firewall, fail2ban, deploy user, hardening);
#   2. uploads the Docker Compose stack + configs + 9route app;
#   3. renders the runtime .env from Terraform variables;
#   4. starts the stack with `docker compose up -d`.
#
# Re-running `terraform apply` re-uploads changed files and restarts the stack,
# giving us reproducible, idempotent configuration management without recreating
# the underlying VPS.

locals {
  remote_base_dir = "/opt/platform"
}

resource "local_file" "compose_env" {
  filename = "${path.module}/../compose/.env"
  content = templatefile("${path.module}/../compose/.env.tftpl", {
    root_domain       = var.root_domain
    letsencrypt_email = var.letsencrypt_email
    timezone          = var.timezone

    postgres_version        = var.postgres_version
    postgres_db             = var.postgres_db
    postgres_admin_user     = var.postgres_admin_user
    postgres_admin_password = replace(var.postgres_admin_password, "$", "$$")

    pgbouncer_version        = var.pgbouncer_version
    pgbouncer_admin_user     = var.pgbouncer_admin_user
    pgbouncer_admin_password = replace(var.pgbouncer_admin_password, "$", "$$")

    redis_version  = var.redis_version
    redis_password = replace(var.redis_password, "$", "$$")

    minio_version       = var.minio_version
    minio_root_user     = var.minio_root_user
    minio_root_password = replace(var.minio_root_password, "$", "$$")

    pgadmin_version  = var.pgadmin_version
    pgadmin_email    = var.pgadmin_email
    pgadmin_password = replace(var.pgadmin_password, "$", "$$")

    grafana_version        = var.grafana_version
    grafana_admin_user     = var.grafana_admin_user
    grafana_admin_password = replace(var.grafana_admin_password, "$", "$$")

    uptime_kuma_version  = var.uptime_kuma_version
    uptime_kuma_user     = var.uptime_kuma_user
    uptime_kuma_password = replace(var.uptime_kuma_password, "$", "$$")

    traefik_version = var.traefik_version
    # Docker Compose's .env parser treats "$" as the start of a variable
    # reference, so any literal "$" inside values rendered into `.env` must be
    # escaped as "$$" before landing on disk.
    traefik_basic_auth = replace(var.traefik_basic_auth, "$", "$$")

    code_server_version       = var.code_server_version
    code_server_password      = replace(var.code_server_password, "$", "$$")
    code_server_sudo_password = replace(var.code_server_sudo_password, "$", "$$")

    prometheus_version    = var.prometheus_version
    loki_version          = var.loki_version
    promtail_version      = var.promtail_version
    node_exporter_version = var.node_exporter_version
    cadvisor_version      = var.cadvisor_version

    ninerouter_package = var.ninerouter_package
    ninerouter_port    = var.ninerouter_port

    restic_repository = replace(var.restic_repository, "$", "$$")
    restic_password   = replace(var.restic_password, "$", "$$")
    restic_environment = {
      for key, value in var.restic_environment : key => replace(value, "$", "$$")
    }
  })

  file_permission = "0600"
}

resource "null_resource" "bootstrap" {
  triggers = {
    bootstrap_script_sha = filesha256("${path.module}/../cloud-init/bootstrap.sh")
    deploy_user          = var.deploy_user
    public_key           = var.public_ssh_key
    initial_ssh_password = var.initial_ssh_password
    initial_ssh_user     = var.initial_ssh_user
    server_ip            = var.server_ip
  }

  # The bootstrap step runs against a Contabo VPS where `deploy_user` does not
  # exist yet. Root access is provisioned via Contabo's "Reset credentials ->
  # SSH Key" panel action, which installs `public_ssh_key` into
  # /root/.ssh/authorized_keys and disables root password auth. So bootstrap
  # authenticates as root using the same private key later used for
  # deploy_user (bootstrap.sh creates deploy_user + its own authorized_keys
  # during this run). All later resources (deploy_stack) switch to
  # deploy_user + private_key once bootstrap has provisioned them.
  connection {
    type        = "ssh"
    host        = var.server_ip
    port        = var.ssh_port
    user        = var.initial_ssh_user
    private_key = file(var.ssh_private_key_path)
    timeout     = "3m"
  }

  provisioner "file" {
    source      = "${path.module}/../cloud-init/bootstrap.sh"
    destination = "/tmp/bootstrap.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x /tmp/bootstrap.sh",
      "DEPLOY_USER='${var.deploy_user}' PUBLIC_SSH_KEY='${var.public_ssh_key}' TIMEZONE='${var.timezone}' REMOTE_BASE_DIR='${local.remote_base_dir}' /tmp/bootstrap.sh",
    ]
  }
}

resource "null_resource" "deploy_stack" {
  depends_on = [null_resource.bootstrap, local_file.compose_env]

  triggers = {
    compose_sha             = filesha256("${path.module}/../compose/docker-compose.yml")
    env_sha                 = local_file.compose_env.content_sha256
    traefik_static_sha      = filesha256("${path.module}/../configs/traefik/traefik.yml")
    traefik_dynamic_sha     = filesha256("${path.module}/../configs/traefik/dynamic.yml")
    grafana_postgres_sha    = filesha256("${path.module}/../configs/grafana/provisioning/datasources/postgres.yml")
    grafana_prometheus_sha  = filesha256("${path.module}/../configs/grafana/provisioning/datasources/prometheus.yml")
    grafana_loki_sha        = filesha256("${path.module}/../configs/grafana/provisioning/datasources/loki.yml")
    prometheus_config_sha   = filesha256("${path.module}/../configs/prometheus/prometheus.yml")
    loki_config_sha         = filesha256("${path.module}/../configs/loki/config.yml")
    promtail_config_sha     = filesha256("${path.module}/../configs/promtail/config.yml")
    ninerouter_dockerfile_sha = filesha256("${path.module}/../apps/9route/Dockerfile")
    backup_postgres_sha     = filesha256("${path.module}/../scripts/backup-postgres.sh")
    backup_minio_sha        = filesha256("${path.module}/../scripts/backup-minio.sh")
    healthcheck_sha         = filesha256("${path.module}/../scripts/healthcheck.sh")
  }

  connection {
    type        = "ssh"
    host        = var.server_ip
    port        = var.ssh_port
    user        = var.deploy_user
    private_key = file(var.ssh_private_key_path)
    timeout     = "3m"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mkdir -p ${local.remote_base_dir}/compose ${local.remote_base_dir}/configs ${local.remote_base_dir}/apps ${local.remote_base_dir}/scripts ${local.remote_base_dir}/data",
      "sudo chown -R ${var.deploy_user}:${var.deploy_user} ${local.remote_base_dir}",
    ]
  }

  provisioner "file" {
    source      = "${path.module}/../compose/docker-compose.yml"
    destination = "${local.remote_base_dir}/compose/docker-compose.yml"
  }

  provisioner "file" {
    source      = local_file.compose_env.filename
    destination = "${local.remote_base_dir}/compose/.env"
  }

  provisioner "file" {
    source      = "${path.module}/../configs/"
    destination = "${local.remote_base_dir}/configs"
  }

  provisioner "file" {
    source      = "${path.module}/../apps/"
    destination = "${local.remote_base_dir}/apps"
  }

  provisioner "file" {
    source      = "${path.module}/../scripts/"
    destination = "${local.remote_base_dir}/scripts"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod +x ${local.remote_base_dir}/scripts/*.sh",
      "mkdir -p ${local.remote_base_dir}/data/{traefik,postgres,redis,minio,pgadmin,grafana,uptime-kuma,code-server,prometheus,loki,promtail,backups,9router}",
      "chmod 700 ${local.remote_base_dir}/data/postgres ${local.remote_base_dir}/data/redis ${local.remote_base_dir}/data/minio ${local.remote_base_dir}/data/pgadmin ${local.remote_base_dir}/data/traefik ${local.remote_base_dir}/data/uptime-kuma ${local.remote_base_dir}/data/code-server ${local.remote_base_dir}/data/promtail || true",
      "chmod 777 ${local.remote_base_dir}/data/grafana ${local.remote_base_dir}/data/prometheus ${local.remote_base_dir}/data/loki ${local.remote_base_dir}/data/9router || true",
      "cd ${local.remote_base_dir}/compose && docker compose build ninerouter",
      "cd ${local.remote_base_dir}/compose && docker compose pull --ignore-buildable",
      "cd ${local.remote_base_dir}/compose && docker compose up -d --remove-orphans",
      "sudo ${local.remote_base_dir}/scripts/install-backup-cron.sh",
    ]
  }
}
