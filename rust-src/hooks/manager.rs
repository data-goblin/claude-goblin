//! Hooks manager for setting up and removing Claude Code hooks.

use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use serde_json::{json, Value};


// Embedded hook scripts
const UV_STANDARD_PY: &str = include_str!("../../src/hooks_data/uv-standard.py");
const BUNDLER_STANDARD_TS: &str = include_str!("../../src/hooks_data/bundler-standard.ts");
const FILE_NAME_CONSISTENCY_SH: &str = include_str!("../../src/hooks_data/file-name-consistency.sh");


/// Hook types available.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum HookType {
    Usage,
    Audio,
    AudioTts,
    Png,
    BundlerStandard,
    FileNameConsistency,
    UvStandard,
}

impl HookType {
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "usage" => Some(Self::Usage),
            "audio" => Some(Self::Audio),
            "audio-tts" => Some(Self::AudioTts),
            "png" => Some(Self::Png),
            "bundler-standard" => Some(Self::BundlerStandard),
            "file-name-consistency" => Some(Self::FileNameConsistency),
            "uv-standard" => Some(Self::UvStandard),
            _ => None,
        }
    }
}


/// Get the settings.json path.
fn get_settings_path(user: bool) -> PathBuf {
    if user {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".claude")
            .join("settings.json")
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(".claude")
            .join("settings.json")
    }
}


/// Get the hook installation path.
fn get_hook_install_path(user: bool) -> PathBuf {
    if user {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(".claude")
            .join("awesome-hooks")
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("."))
            .join(".claude")
            .join("hooks")
    }
}


/// Load settings from settings.json.
fn load_settings(settings_path: &Path) -> Result<Value> {
    if settings_path.exists() {
        let content = fs::read_to_string(settings_path)
            .with_context(|| format!("Failed to read {}", settings_path.display()))?;
        serde_json::from_str(&content)
            .with_context(|| format!("Failed to parse {}", settings_path.display()))
    } else {
        Ok(json!({}))
    }
}


/// Save settings to settings.json.
fn save_settings(settings_path: &Path, settings: &Value) -> Result<()> {
    // Ensure parent directory exists
    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent)?;
    }

    let content = serde_json::to_string_pretty(settings)?;
    fs::write(settings_path, content)
        .with_context(|| format!("Failed to write {}", settings_path.display()))?;

    Ok(())
}


/// Initialize hooks structure in settings.
fn init_hooks_structure(settings: &mut Value) {
    if settings.get("hooks").is_none() {
        settings["hooks"] = json!({});
    }

    let hooks = settings["hooks"].as_object_mut().unwrap();

    if !hooks.contains_key("Stop") {
        hooks.insert("Stop".to_string(), json!([]));
    }
    if !hooks.contains_key("Notification") {
        hooks.insert("Notification".to_string(), json!([]));
    }
    if !hooks.contains_key("PreCompact") {
        hooks.insert("PreCompact".to_string(), json!([]));
    }
    if !hooks.contains_key("PreToolUse") {
        hooks.insert("PreToolUse".to_string(), json!([]));
    }
}


/// Install a hook script to the hooks directory.
fn install_hook_script(hook_type: HookType, user: bool) -> Result<PathBuf> {
    let install_dir = get_hook_install_path(user);
    fs::create_dir_all(&install_dir)?;

    let (filename, content) = match hook_type {
        HookType::UvStandard => ("uv-standard.py", UV_STANDARD_PY),
        HookType::BundlerStandard => ("bundler-standard.ts", BUNDLER_STANDARD_TS),
        HookType::FileNameConsistency => ("file-name-consistency.sh", FILE_NAME_CONSISTENCY_SH),
        _ => return Err(anyhow::anyhow!("Hook type does not require script installation")),
    };

    let script_path = install_dir.join(filename);
    fs::write(&script_path, content)?;

    // Make executable on Unix
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;
    }

    Ok(script_path)
}


/// Check if a hook matches a pattern.
fn hook_matches(hook: &Value, patterns: &[&str]) -> bool {
    if let Some(hooks_array) = hook.get("hooks").and_then(|h| h.as_array()) {
        for h in hooks_array {
            if let Some(cmd) = h.get("command").and_then(|c| c.as_str()) {
                for pattern in patterns {
                    if cmd.contains(pattern) {
                        return true;
                    }
                }
            }
        }
    }
    false
}


/// Get sound command for platform.
fn get_sound_command(sound_name: &str) -> Option<String> {
    #[cfg(target_os = "macos")]
    {
        Some(format!("afplay /System/Library/Sounds/{}.aiff &", sound_name))
    }

    #[cfg(target_os = "windows")]
    {
        Some(format!(
            r#"powershell -c "(New-Object Media.SoundPlayer 'C:\Windows\Media\{}.wav').PlaySync();" &"#,
            sound_name
        ))
    }

    #[cfg(target_os = "linux")]
    {
        Some(format!(
            "(paplay /usr/share/sounds/freedesktop/stereo/{}.oga 2>/dev/null || aplay /usr/share/sounds/alsa/{}.wav 2>/dev/null) &",
            sound_name, sound_name
        ))
    }

    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        None
    }
}


/// Setup hooks.
pub fn setup_hooks(hook_type: Option<&str>, user: bool) -> Result<()> {
    let settings_path = get_settings_path(user);
    let scope = if user { "user" } else { "project" };

    // Parse hook type
    let parsed_type = hook_type.and_then(HookType::from_str);

    if hook_type.is_some() && parsed_type.is_none() {
        eprintln!("\x1b[31mUnknown hook type: {}\x1b[0m", hook_type.unwrap());
        eprintln!("Valid types: usage, audio, audio-tts, png, bundler-standard, file-name-consistency, uv-standard");
        return Ok(());
    }

    // Show menu if no type specified
    if hook_type.is_none() {
        println!("\x1b[1m\x1b[36mAvailable hooks to set up:\x1b[0m\n");
        println!("\x1b[1mClaude Goblin hooks:\x1b[0m");
        println!("  \x1b[1musage\x1b[0m                - Auto-track usage after each response");
        println!("  \x1b[1maudio\x1b[0m                - Play sounds for completion & permission requests");
        println!("  \x1b[1maudio-tts\x1b[0m            - Speak permission requests using TTS (macOS only)");
        println!("  \x1b[1mpng\x1b[0m                  - Auto-update usage PNG after each response\n");
        println!("\x1b[1mAwesome-hooks (PreToolUse):\x1b[0m");
        println!("  \x1b[1mbundler-standard\x1b[0m     - Enforce Bun instead of npm/pnpm/yarn");
        println!("  \x1b[1mfile-name-consistency\x1b[0m - Ensure consistent file naming");
        println!("  \x1b[1muv-standard\x1b[0m          - Enforce uv instead of pip/pip3\n");
        println!("Usage: ccg setup hooks <type> [--user]");
        println!("Example: ccg setup hooks usage              (project-level)");
        println!("Example: ccg setup hooks usage --user       (user-level)");
        println!("Example: ccg setup hooks uv-standard        (project-level)");
        return Ok(());
    }

    let hook_type = parsed_type.unwrap();

    println!("\x1b[1m\x1b[36mSetting up {:?} hook ({}-level)\x1b[0m\n", hook_type, scope);

    // Ensure .claude directory exists
    if let Some(parent) = settings_path.parent() {
        fs::create_dir_all(parent)?;
    }

    // Load settings
    let mut settings = load_settings(&settings_path)?;
    init_hooks_structure(&mut settings);

    // Setup the specific hook
    match hook_type {
        HookType::Usage => setup_usage_hook(&mut settings)?,
        HookType::Audio => setup_audio_hook(&mut settings)?,
        HookType::AudioTts => setup_audio_tts_hook(&mut settings, user)?,
        HookType::Png => setup_png_hook(&mut settings)?,
        HookType::BundlerStandard => setup_pretooluse_hook(&mut settings, hook_type, user)?,
        HookType::FileNameConsistency => setup_pretooluse_hook(&mut settings, hook_type, user)?,
        HookType::UvStandard => setup_pretooluse_hook(&mut settings, hook_type, user)?,
    }

    // Save settings
    save_settings(&settings_path, &settings)?;

    println!("\n\x1b[2mHook location: {}\x1b[0m", settings_path.display());
    println!("\x1b[2mTo remove: ccg remove hooks {:?}{}\x1b[0m",
        hook_type,
        if user { " --user" } else { "" }
    );

    Ok(())
}


/// Setup usage tracking hook.
fn setup_usage_hook(settings: &mut Value) -> Result<()> {
    let hook_command = "ccg update usage > /dev/null 2>&1 &";

    // Check if already exists
    let stop_hooks = settings["hooks"]["Stop"].as_array().unwrap();
    let exists = stop_hooks.iter().any(|h| {
        hook_matches(h, &["ccg update usage", "claude-goblin update usage", "ccg update-usage"])
    });

    if exists {
        println!("\x1b[33mUsage tracking hook already configured!\x1b[0m");
        return Ok(());
    }

    // Add hook
    let new_hook = json!({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    });

    settings["hooks"]["Stop"].as_array_mut().unwrap().push(new_hook);

    println!("\x1b[32m+ Successfully configured usage tracking hook\x1b[0m");
    println!("\n\x1b[1mWhat this does:\x1b[0m");
    println!("  - Runs after each Claude response completes");
    println!("  - Saves usage data to database");
    println!("  - Runs silently in the background");

    Ok(())
}


/// Setup audio notification hook.
fn setup_audio_hook(settings: &mut Value) -> Result<()> {
    // Default sounds
    #[cfg(target_os = "macos")]
    let (completion_sound, permission_sound, compaction_sound) = ("Glass", "Ping", "Purr");

    #[cfg(target_os = "windows")]
    let (completion_sound, permission_sound, compaction_sound) = ("Windows Notify", "Windows Ding", "chimes");

    #[cfg(target_os = "linux")]
    let (completion_sound, permission_sound, compaction_sound) = ("complete", "bell", "message");

    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        println!("\x1b[31mAudio hooks not supported on this platform\x1b[0m");
        return Ok(());
    }

    let completion_cmd = get_sound_command(completion_sound);
    let permission_cmd = get_sound_command(permission_sound);
    let compaction_cmd = get_sound_command(compaction_sound);

    if completion_cmd.is_none() {
        println!("\x1b[31mAudio hooks not supported on this platform\x1b[0m");
        return Ok(());
    }

    // Remove existing audio hooks
    let audio_patterns = &["afplay", "powershell", "paplay", "aplay"];

    if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
        arr.retain(|h| !hook_matches(h, audio_patterns));
    }
    if let Some(arr) = settings["hooks"]["Notification"].as_array_mut() {
        arr.retain(|h| !hook_matches(h, audio_patterns));
    }
    if let Some(arr) = settings["hooks"]["PreCompact"].as_array_mut() {
        arr.retain(|h| !hook_matches(h, audio_patterns));
    }

    // Add new hooks
    settings["hooks"]["Stop"].as_array_mut().unwrap().push(json!({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": completion_cmd.unwrap()
        }]
    }));

    settings["hooks"]["Notification"].as_array_mut().unwrap().push(json!({
        "hooks": [{
            "type": "command",
            "command": permission_cmd.unwrap()
        }]
    }));

    settings["hooks"]["PreCompact"].as_array_mut().unwrap().push(json!({
        "hooks": [{
            "type": "command",
            "command": compaction_cmd.unwrap()
        }]
    }));

    println!("\x1b[32m+ Successfully configured audio notification hooks\x1b[0m");
    println!("\n\x1b[1mWhat this does:\x1b[0m");
    println!("  - Completion sound ({}): Plays when Claude finishes responding", completion_sound);
    println!("  - Permission sound ({}): Plays when Claude requests permission", permission_sound);
    println!("  - Compaction sound ({}): Plays before conversation compaction", compaction_sound);
    println!("  - All hooks run in the background");

    Ok(())
}


/// Setup audio TTS hook (cross-platform).
fn setup_audio_tts_hook(settings: &mut Value, user: bool) -> Result<()> {
    #[cfg(not(any(target_os = "macos", target_os = "windows", target_os = "linux")))]
    {
        println!("\x1b[31mAudio TTS hook is not supported on this platform\x1b[0m");
        return Ok(());
    }

    println!("\x1b[1m\x1b[36mSetting up Audio TTS Hook\x1b[0m\n");
    println!("\x1b[2mThis hook speaks messages aloud using text-to-speech.\x1b[0m\n");

    // Hook type selection
    println!("\x1b[1mWhich hooks do you want to enable TTS for?\x1b[0m");
    println!("  1. Notification only (permission requests) [recommended]");
    println!("  2. Stop only (when Claude finishes responding)");
    println!("  3. PreCompact only (before conversation compaction)");
    println!("  4. Notification + Stop");
    println!("  5. All three");

    print!("\n\x1b[2mEnter number (default: 1):\x1b[0m ");
    io::stdout().flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    let input = input.trim();

    let hook_types: Vec<&str> = match input {
        "" | "1" => vec!["Notification"],
        "2" => vec!["Stop"],
        "3" => vec!["PreCompact"],
        "4" => vec!["Notification", "Stop"],
        "5" => vec!["Notification", "Stop", "PreCompact"],
        _ => {
            println!("\x1b[33mInvalid selection, using default (Notification only)\x1b[0m");
            vec!["Notification"]
        }
    };

    // Voice selection
    #[cfg(target_os = "macos")]
    let voices = vec![
        ("Samantha", "Clear, natural female voice"),
        ("Alex", "Clear, natural male voice"),
        ("Daniel", "British English male voice"),
        ("Karen", "Australian English female voice"),
        ("Fred", "Classic robotic voice"),
    ];

    #[cfg(target_os = "windows")]
    let voices = vec![
        ("Microsoft David", "Default male voice"),
        ("Microsoft Zira", "Default female voice"),
    ];

    #[cfg(target_os = "linux")]
    let voices = vec![
        ("default", "Default espeak voice"),
        ("en-us", "US English"),
        ("en-gb", "British English"),
    ];

    println!("\n\x1b[1mChoose a voice for TTS:\x1b[0m");
    for (idx, (name, desc)) in voices.iter().enumerate() {
        println!("  {}. {} - {}", idx + 1, name, desc);
    }

    print!("\n\x1b[2mEnter number (default: 1):\x1b[0m ");
    io::stdout().flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;
    let input = input.trim();

    let voice = if input.is_empty() {
        voices[0].0
    } else if let Ok(idx) = input.parse::<usize>() {
        if idx >= 1 && idx <= voices.len() {
            voices[idx - 1].0
        } else {
            println!("\x1b[33mInvalid selection, using default\x1b[0m");
            voices[0].0
        }
    } else {
        println!("\x1b[33mInvalid selection, using default\x1b[0m");
        voices[0].0
    };

    // Create the hook script
    let script_dir = get_hook_install_path(user);
    fs::create_dir_all(&script_dir)?;

    #[cfg(target_os = "macos")]
    let script_content = format!(r#"#!/bin/bash
# Audio TTS Hook for Claude Code (macOS)
json_input=$(cat)
message=$(echo "$json_input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    hook = data.get('hook_event_name', '')
    if hook == 'Notification':
        print(data.get('message', 'Claude requesting permission'))
    elif hook == 'Stop':
        print('Claude finished responding')
    elif hook == 'PreCompact':
        print('Compacting conversation')
    else:
        print('Claude event')
except:
    print('Claude event')
")
echo "$message" | say -v {} &
"#, voice);

    #[cfg(target_os = "windows")]
    let script_content = format!(r#"@echo off
setlocal enabledelayedexpansion
set /p json=
powershell -Command "Add-Type -AssemblyName System.Speech; $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; $synth.SelectVoice('{}'); $synth.Speak('Claude event')"
"#, voice);

    #[cfg(target_os = "linux")]
    let script_content = format!(r#"#!/bin/bash
# Audio TTS Hook for Claude Code (Linux)
json_input=$(cat)
message=$(echo "$json_input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    hook = data.get('hook_event_name', '')
    if hook == 'Notification':
        print(data.get('message', 'Claude requesting permission'))
    elif hook == 'Stop':
        print('Claude finished responding')
    elif hook == 'PreCompact':
        print('Compacting conversation')
    else:
        print('Claude event')
except:
    print('Claude event')
")
espeak -v {} "$message" &
"#, voice);

    #[cfg(target_os = "windows")]
    let script_name = "audio_tts_hook.bat";
    #[cfg(not(target_os = "windows"))]
    let script_name = "audio_tts_hook.sh";

    let script_path = script_dir.join(script_name);
    fs::write(&script_path, script_content)?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = fs::metadata(&script_path)?.permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script_path, perms)?;
    }

    // Remove existing TTS and audio hooks
    let tts_patterns = &["audio_tts_hook", "say -v", "espeak"];
    let audio_patterns = &["afplay", "powershell", "paplay", "aplay"];

    for hook_type in &hook_types {
        if let Some(arr) = settings["hooks"][*hook_type].as_array_mut() {
            arr.retain(|h| !hook_matches(h, tts_patterns) && !hook_matches(h, audio_patterns));
        }
    }

    // Add new TTS hooks
    for hook_type in &hook_types {
        let mut hook_config = json!({
            "hooks": [{
                "type": "command",
                "command": script_path.to_string_lossy()
            }]
        });

        if *hook_type == "Stop" {
            hook_config["matcher"] = json!("*");
        }

        settings["hooks"][*hook_type].as_array_mut().unwrap().push(hook_config);
    }

    println!("\x1b[32m+ Successfully configured audio TTS hooks\x1b[0m");
    println!("\n\x1b[1mWhat this does:\x1b[0m");
    for hook_type in &hook_types {
        match *hook_type {
            "Notification" => println!("  - Speaks permission request messages aloud"),
            "Stop" => println!("  - Announces when Claude finishes responding"),
            "PreCompact" => println!("  - Announces before conversation compaction"),
            _ => {}
        }
    }
    println!("  - Uses the '{}' voice", voice);
    println!("\n\x1b[2mHook script: {}\x1b[0m", script_path.display());

    Ok(())
}


/// Setup PNG auto-export hook.
fn setup_png_hook(settings: &mut Value) -> Result<()> {
    let hook_command = "ccg export --fast > /dev/null 2>&1 &";

    // Check if already exists
    let stop_hooks = settings["hooks"]["Stop"].as_array().unwrap();
    let exists = stop_hooks.iter().any(|h| {
        hook_matches(h, &["ccg export", "claude-goblin export"])
    });

    if exists {
        println!("\x1b[33mPNG auto-export hook already configured!\x1b[0m");
        return Ok(());
    }

    // Add hook
    let new_hook = json!({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": hook_command
        }]
    });

    settings["hooks"]["Stop"].as_array_mut().unwrap().push(new_hook);

    println!("\x1b[32m+ Successfully configured PNG auto-export hook\x1b[0m");
    println!("\n\x1b[1mWhat this does:\x1b[0m");
    println!("  - Runs after each Claude response completes");
    println!("  - Updates usage heatmap PNG in ~/.claude/usage/");
    println!("  - Runs silently in the background");

    Ok(())
}


/// Setup PreToolUse hook (bundler-standard, file-name-consistency, uv-standard).
fn setup_pretooluse_hook(settings: &mut Value, hook_type: HookType, user: bool) -> Result<()> {
    // Install the script
    let script_path = install_hook_script(hook_type, user)?;

    let (matcher, hook_name, description, requirements) = match hook_type {
        HookType::BundlerStandard => (
            "Bash",
            "bundler-standard",
            vec![
                "Intercepts npm/pnpm/yarn commands in Bash",
                "Blocks them and suggests Bun equivalents",
                "Ensures you use Bun for package management",
            ],
            "Bun runtime installed (https://bun.sh)",
        ),
        HookType::FileNameConsistency => (
            "Bash|Write|MultiEdit",
            "file-name-consistency",
            vec![
                "Analyzes your project's file naming patterns",
                "Blocks files with inconsistent naming",
                "Suggests correctly formatted filenames",
            ],
            "GEMINI_API_KEY environment variable",
        ),
        HookType::UvStandard => (
            "Bash",
            "uv-standard",
            vec![
                "Intercepts pip/pip3 commands in Bash",
                "Blocks them and suggests uv equivalents",
                "Ensures you use uv for Python package management",
            ],
            "uv package installer (https://github.com/astral-sh/uv)",
        ),
        _ => return Err(anyhow::anyhow!("Invalid hook type for PreToolUse")),
    };

    // Check if already exists
    let pretooluse_hooks = settings["hooks"]["PreToolUse"].as_array().unwrap();
    let exists = pretooluse_hooks.iter().any(|h| {
        hook_matches(h, &[hook_name])
    });

    if exists {
        println!("\x1b[33m{} hook already configured!\x1b[0m", hook_name);
        return Ok(());
    }

    // Add hook
    let new_hook = json!({
        "matcher": matcher,
        "hooks": [{
            "type": "command",
            "command": script_path.to_string_lossy()
        }]
    });

    settings["hooks"]["PreToolUse"].as_array_mut().unwrap().push(new_hook);

    println!("\x1b[32m+ Successfully configured {} hook\x1b[0m", hook_name);
    println!("\n\x1b[1mWhat this does:\x1b[0m");
    for desc in description {
        println!("  - {}", desc);
    }
    println!("\n\x1b[1m\x1b[36mRequirements:\x1b[0m");
    println!("  - {}", requirements);

    Ok(())
}


/// Remove hooks.
pub fn remove_hooks(hook_type: Option<&str>, user: bool) -> Result<()> {
    let settings_path = get_settings_path(user);
    let scope = if user { "user" } else { "project" };

    if !settings_path.exists() {
        println!("\x1b[33mNo Claude Code settings file found at {} level.\x1b[0m", scope);
        return Ok(());
    }

    // Parse hook type
    let parsed_type = hook_type.and_then(HookType::from_str);

    if hook_type.is_some() && parsed_type.is_none() {
        eprintln!("\x1b[31mUnknown hook type: {}\x1b[0m", hook_type.unwrap());
        eprintln!("Valid types: usage, audio, audio-tts, png, bundler-standard, file-name-consistency, uv-standard");
        return Ok(());
    }

    println!("\x1b[1m\x1b[36mRemoving hooks ({}-level)\x1b[0m\n", scope);

    // Load settings
    let mut settings = load_settings(&settings_path)?;

    if settings.get("hooks").is_none() {
        println!("\x1b[33mNo hooks configured.\x1b[0m");
        return Ok(());
    }

    init_hooks_structure(&mut settings);

    // Create backup
    let backup_path = settings_path.with_extension("json.bak");
    fs::copy(&settings_path, &backup_path)?;
    println!("\x1b[2mBackup created: {}\x1b[0m\n", backup_path.display());

    // Count hooks before
    let count_hooks = |arr: &Value| -> usize {
        arr.as_array().map(|a| a.len()).unwrap_or(0)
    };

    let before_stop = count_hooks(&settings["hooks"]["Stop"]);
    let before_notification = count_hooks(&settings["hooks"]["Notification"]);
    let before_precompact = count_hooks(&settings["hooks"]["PreCompact"]);
    let before_pretooluse = count_hooks(&settings["hooks"]["PreToolUse"]);

    // Remove hooks based on type
    let removed_type = match parsed_type {
        Some(HookType::Usage) => {
            let patterns = &["ccg update usage", "claude-goblin update usage", "ccg update-usage"];
            if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            "usage tracking"
        }
        Some(HookType::Audio) => {
            let patterns = &["afplay", "powershell", "paplay", "aplay"];
            if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            if let Some(arr) = settings["hooks"]["Notification"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            if let Some(arr) = settings["hooks"]["PreCompact"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            "audio notification"
        }
        Some(HookType::AudioTts) => {
            let patterns = &["say "];
            if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            if let Some(arr) = settings["hooks"]["Notification"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            if let Some(arr) = settings["hooks"]["PreCompact"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            "audio TTS"
        }
        Some(HookType::Png) => {
            let patterns = &["ccg export", "claude-goblin export"];
            if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, patterns));
            }
            "PNG auto-export"
        }
        Some(HookType::BundlerStandard) => {
            if let Some(arr) = settings["hooks"]["PreToolUse"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, &["bundler-standard"]));
            }
            "bundler-standard"
        }
        Some(HookType::FileNameConsistency) => {
            if let Some(arr) = settings["hooks"]["PreToolUse"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, &["file-name-consistency"]));
            }
            "file-name-consistency"
        }
        Some(HookType::UvStandard) => {
            if let Some(arr) = settings["hooks"]["PreToolUse"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, &["uv-standard"]));
            }
            "uv-standard"
        }
        None => {
            // Remove all claude-goblin hooks
            let all_patterns = &[
                "ccg update usage", "claude-goblin update usage", "ccg update-usage",
                "afplay", "powershell", "paplay", "aplay",
                "say ",
                "ccg export", "claude-goblin export",
            ];
            let pretooluse_patterns = &["bundler-standard", "file-name-consistency", "uv-standard"];

            if let Some(arr) = settings["hooks"]["Stop"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, all_patterns));
            }
            if let Some(arr) = settings["hooks"]["Notification"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, all_patterns));
            }
            if let Some(arr) = settings["hooks"]["PreCompact"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, all_patterns));
            }
            if let Some(arr) = settings["hooks"]["PreToolUse"].as_array_mut() {
                arr.retain(|h| !hook_matches(h, pretooluse_patterns));
            }
            "all claude-goblin"
        }
    };

    // Count hooks after
    let after_stop = count_hooks(&settings["hooks"]["Stop"]);
    let after_notification = count_hooks(&settings["hooks"]["Notification"]);
    let after_precompact = count_hooks(&settings["hooks"]["PreCompact"]);
    let after_pretooluse = count_hooks(&settings["hooks"]["PreToolUse"]);

    let removed_count = (before_stop - after_stop)
        + (before_notification - after_notification)
        + (before_precompact - after_precompact)
        + (before_pretooluse - after_pretooluse);

    if removed_count == 0 {
        println!("\x1b[33mNo {} hooks found to remove.\x1b[0m", removed_type);
        return Ok(());
    }

    // Save settings
    save_settings(&settings_path, &settings)?;

    println!("\x1b[32m+ Removed {} {} hook(s)\x1b[0m", removed_count, removed_type);
    println!("\x1b[2mSettings file: {}\x1b[0m", settings_path.display());

    Ok(())
}
