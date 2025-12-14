//! Setup subcommands.

use std::fs;
use std::path::PathBuf;

use anyhow::Result;


/// Setup devcontainer for safe Claude Code execution.
pub fn container(
    target: Option<&str>,
    name: Option<&str>,
    domains: Option<&str>,
    no_vscode: bool,
) -> Result<()> {
    let target_dir = target
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));

    let project_name = name
        .map(String::from)
        .unwrap_or_else(|| {
            target_dir
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("project")
                .to_string()
        });

    let extra_domains: Vec<&str> = domains
        .map(|d| d.split(',').map(|s| s.trim()).collect())
        .unwrap_or_default();

    println!("\x1b[1m\x1b[36mSetting up devcontainer for {}\x1b[0m\n", project_name);

    // Create .devcontainer directory
    let devcontainer_dir = target_dir.join(".devcontainer");
    fs::create_dir_all(&devcontainer_dir)?;

    // Generate devcontainer.json
    let devcontainer_json = generate_devcontainer_json(&project_name, &extra_domains);
    fs::write(devcontainer_dir.join("devcontainer.json"), devcontainer_json)?;
    println!("\x1b[32m+ Created .devcontainer/devcontainer.json\x1b[0m");

    // Generate Dockerfile
    let dockerfile = generate_dockerfile();
    fs::write(devcontainer_dir.join("Dockerfile"), dockerfile)?;
    println!("\x1b[32m+ Created .devcontainer/Dockerfile\x1b[0m");

    // Generate .vscode/settings.json if not --no-vscode
    if !no_vscode {
        let vscode_dir = target_dir.join(".vscode");
        fs::create_dir_all(&vscode_dir)?;

        let settings_path = vscode_dir.join("settings.json");
        if !settings_path.exists() {
            let vscode_settings = generate_vscode_settings();
            fs::write(&settings_path, vscode_settings)?;
            println!("\x1b[32m+ Created .vscode/settings.json\x1b[0m");
        } else {
            println!("\x1b[33m! .vscode/settings.json already exists, skipping\x1b[0m");
        }
    }

    println!("\n\x1b[1mNext steps:\x1b[0m");
    println!("  1. Open this folder in VS Code");
    println!("  2. When prompted, click 'Reopen in Container'");
    println!("  3. Or run: Dev Containers: Reopen in Container from command palette");
    println!("\n\x1b[2mNote: Claude Code will be sandboxed to this container for safety.\x1b[0m");

    Ok(())
}


/// Generate devcontainer.json content.
fn generate_devcontainer_json(project_name: &str, extra_domains: &[&str]) -> String {
    let mut allowed_hosts = vec![
        "github.com".to_string(),
        "api.github.com".to_string(),
        "raw.githubusercontent.com".to_string(),
        "pypi.org".to_string(),
        "files.pythonhosted.org".to_string(),
        "registry.npmjs.org".to_string(),
        "crates.io".to_string(),
    ];

    for domain in extra_domains {
        if !domain.is_empty() {
            allowed_hosts.push(domain.to_string());
        }
    }

    let _hosts_json: String = allowed_hosts
        .iter()
        .map(|h| format!("      \"{}\"", h))
        .collect::<Vec<_>>()
        .join(",\n");

    format!(r#"{{
  "name": "{project_name}",
  "build": {{
    "dockerfile": "Dockerfile",
    "context": ".."
  }},
  "customizations": {{
    "vscode": {{
      "settings": {{
        "terminal.integrated.defaultProfile.linux": "bash"
      }},
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "anthropic.claude-code"
      ]
    }}
  }},
  "remoteUser": "vscode",
  "features": {{
    "ghcr.io/devcontainers/features/common-utils:2": {{
      "installZsh": "true",
      "username": "vscode",
      "userUid": "1000",
      "userGid": "1000"
    }},
    "ghcr.io/devcontainers/features/python:1": {{
      "version": "3.12"
    }},
    "ghcr.io/devcontainers/features/node:1": {{
      "version": "20"
    }}
  }},
  "postCreateCommand": "pip install --upgrade pip && npm install -g npm",
  "env": {{
    "CLAUDE_CODE_SANDBOX_NETWORK_ALLOWED_HOSTS": "{hosts_list}"
  }}
}}"#,
        project_name = project_name,
        hosts_list = allowed_hosts.join(",")
    )
}


/// Generate Dockerfile content.
fn generate_dockerfile() -> String {
    r#"FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Install additional tools
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    jq \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up PATH for uv
ENV PATH="/root/.local/bin:${PATH}"

# Set working directory
WORKDIR /workspace
"#.to_string()
}


/// Generate VS Code settings.json content.
fn generate_vscode_settings() -> String {
    r#"{
  "python.defaultInterpreterPath": "/usr/local/bin/python",
  "python.terminal.activateEnvironment": true,
  "terminal.integrated.defaultProfile.linux": "bash"
}
"#.to_string()
}
