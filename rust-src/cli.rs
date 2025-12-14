//! CLI definitions using clap.

use clap::{Parser, Subcommand};


/// Claude Goblin - CLI for Claude Code usage tracking and analytics
#[derive(Parser)]
#[command(name = "ccg")]
#[command(author, version, about, long_about = None)]
pub struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}


#[derive(Subcommand)]
enum Commands {
    /// Show usage dashboard with KPI cards and breakdowns
    Usage {
        /// Auto-refresh dashboard every 5 seconds
        #[arg(long)]
        live: bool,

        /// Skip updates, read from database only (faster)
        #[arg(long)]
        fast: bool,

        /// Anonymize project names
        #[arg(long)]
        anon: bool,
    },

    /// Show detailed statistics and cost analysis
    Stats {
        /// Skip updates, read from database only (faster)
        #[arg(long)]
        fast: bool,
    },

    /// Export yearly heatmap as PNG or SVG
    Export {
        /// Export as SVG instead of PNG
        #[arg(long)]
        svg: bool,

        /// Open file after export
        #[arg(long)]
        open: bool,

        /// Skip updates, read from database only (faster)
        #[arg(long)]
        fast: bool,

        /// Filter by year (default: current year)
        #[arg(short, long)]
        year: Option<i32>,

        /// Output file path
        #[arg(short, long)]
        output: Option<String>,
    },

    /// Setup integrations and configurations
    Setup {
        #[command(subcommand)]
        command: SetupCommands,
    },

    /// Remove integrations and configurations
    Remove {
        #[command(subcommand)]
        command: RemoveCommands,
    },

    /// Update data
    Update {
        #[command(subcommand)]
        command: UpdateCommands,
    },

    /// Restore from backup
    Restore {
        #[command(subcommand)]
        command: RestoreCommands,
    },

    /// Launch macOS menu bar app (macOS only)
    #[command(name = "status-bar")]
    StatusBar,
}


#[derive(Subcommand)]
enum SetupCommands {
    /// Setup Claude Code hooks for automation
    Hooks {
        /// Hook type: usage, audio, audio-tts, png, uv-standard, bundler-standard, file-name-consistency
        hook_type: Option<String>,

        /// Install hooks at user level (~/.claude/) instead of project level
        #[arg(long)]
        user: bool,
    },

    /// Setup devcontainer for safe Claude Code execution
    Container {
        /// Target directory (default: current directory)
        target: Option<String>,

        /// Project name (default: directory name)
        #[arg(short, long)]
        name: Option<String>,

        /// Extra domains to whitelist (comma-separated)
        #[arg(short, long)]
        domains: Option<String>,

        /// Skip creating .vscode/settings.json
        #[arg(long)]
        no_vscode: bool,
    },
}


#[derive(Subcommand)]
enum RemoveCommands {
    /// Remove Claude Code hooks
    Hooks {
        /// Hook type to remove (leave empty for all)
        hook_type: Option<String>,

        /// Remove hooks from user level (~/.claude/)
        #[arg(long)]
        user: bool,
    },

    /// Remove historical usage database
    Usage {
        /// Force deletion without confirmation
        #[arg(short, long)]
        force: bool,
    },
}


#[derive(Subcommand)]
enum UpdateCommands {
    /// Update historical database with latest data
    Usage,
}


#[derive(Subcommand)]
enum RestoreCommands {
    /// Restore database from backup file
    Usage,
}


/// Run the CLI
pub fn run() -> anyhow::Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Usage { live, fast, anon }) => {
            println!("Usage command: live={live}, fast={fast}, anon={anon}");
            println!("(Not yet implemented)");
        }
        Some(Commands::Stats { fast }) => {
            println!("Stats command: fast={fast}");
            println!("(Not yet implemented)");
        }
        Some(Commands::Export { svg, open, fast, year, output }) => {
            println!("Export command: svg={svg}, open={open}, fast={fast}, year={year:?}, output={output:?}");
            println!("(Not yet implemented)");
        }
        Some(Commands::Setup { command }) => {
            match command {
                SetupCommands::Hooks { hook_type, user } => {
                    println!("Setup hooks: type={hook_type:?}, user={user}");
                    println!("(Not yet implemented)");
                }
                SetupCommands::Container { target, name, domains, no_vscode } => {
                    println!("Setup container: target={target:?}, name={name:?}, domains={domains:?}, no_vscode={no_vscode}");
                    println!("(Not yet implemented)");
                }
            }
        }
        Some(Commands::Remove { command }) => {
            match command {
                RemoveCommands::Hooks { hook_type, user } => {
                    println!("Remove hooks: type={hook_type:?}, user={user}");
                    println!("(Not yet implemented)");
                }
                RemoveCommands::Usage { force } => {
                    println!("Remove usage: force={force}");
                    println!("(Not yet implemented)");
                }
            }
        }
        Some(Commands::Update { command }) => {
            match command {
                UpdateCommands::Usage => {
                    println!("Update usage");
                    println!("(Not yet implemented)");
                }
            }
        }
        Some(Commands::Restore { command }) => {
            match command {
                RestoreCommands::Usage => {
                    println!("Restore usage");
                    println!("(Not yet implemented)");
                }
            }
        }
        Some(Commands::StatusBar) => {
            println!("Status bar");
            println!("(Not yet implemented - macOS only)");
        }
        None => {
            // No subcommand, show help
            use clap::CommandFactory;
            Cli::command().print_help()?;
        }
    }

    Ok(())
}
