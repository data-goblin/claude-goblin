#!/usr/bin/env bun

interface HookEvent {
  tool_name: string;
  tool_input: any;
  session_id?: string;
  transcript_path?: string;
}

// PreToolUse hook that enforces bun usage over npm/pnpm/yarn
function preToolUse(event: HookEvent): void {
  // Only check Bash tool calls
  if (event.tool_name !== 'Bash') {
    return;
  }

  const command = event.tool_input?.command || '';
  
  // Skip git commands entirely - we don't want to interfere with commit messages
  if (command.startsWith('git ')) {
    return;
  }
  
  // Check for npm, pnpm, yarn usage, and their executable tools
  const packageManagerPattern = /\b(npm|pnpm|yarn|npx)(\s+|$)/i;
  const match = command.match(packageManagerPattern);
  
  if (match) {
    const packageManager = match[1].toLowerCase();
    
    // Commands that map directly to bun (same subcommand)
    const directMappings = new Set([
      'init', 'install', 'add', 'remove', 'run', 'test', 'update', 
      'outdated', 'link', 'unlink', 'publish'
    ]);
    
    // Special command mappings
    const specialMappings: Record<string, string> = {
      'i': 'install',
      'rm': 'remove',
      'uninstall': 'remove',
      'exec': 'x',
      'ci': 'install --frozen-lockfile',
      'ls': 'pm ls',
      'list': 'pm ls',
      // npm specific
      'pack': 'bunx npm pack',
      'cache clean': 'pm cache rm',
      'audit': 'bunx npm audit',
      'fund': 'bunx npm fund',
      'doctor': 'bunx npm doctor',
      // pnpm specific
      'dlx': 'bunx',
      'store prune': 'pm cache rm',
      // yarn specific
      'upgrade': 'update',
      'global add': 'add -g',
      'global remove': 'remove -g'
    };
    
    // Parse the command after the package manager
    const commandParts = command.substring(match.index! + match[0].length).trim();
    const words = commandParts.split(/\s+/);
    const subcommand = words[0] || '';
    const args = words.slice(1).join(' ');
    
    let bunEquivalent = '';
    
    // Handle npx specifically - it's always mapped to bunx
    if (packageManager === 'npx') {
      bunEquivalent = `bunx ${commandParts}`;
    } else {
      // Check for multi-word commands first (e.g., "cache clean", "global add")
      const multiWordCommand = words.slice(0, 2).join(' ');
      if (specialMappings[multiWordCommand]) {
        bunEquivalent = `bun ${specialMappings[multiWordCommand]} ${words.slice(2).join(' ')}`.trim();
      } else if (specialMappings[subcommand]) {
        // Check single word special mappings
        bunEquivalent = `bun ${specialMappings[subcommand]} ${args}`.trim();
      } else if (directMappings.has(subcommand)) {
        // Direct mapping - just replace package manager with bun
        bunEquivalent = `bun ${commandParts}`;
      } else if (!subcommand) {
        // Just the package manager alone
        bunEquivalent = 'bun';
      } else {
        // Unknown command - fallback to generic replacement
        bunEquivalent = `bun ${commandParts}`;
      }
    }
    
    console.error(`❌ Blocked: ${packageManager} is not allowed in this project.`);
    console.error(`✅ Please use bun instead: ${bunEquivalent}`);
    console.error(`Run this command instead: ${bunEquivalent}`);

    // Status code 2 = "error, feedback to Claude itself which you use for substitution"
    process.exit(2);
  }
}

// Main execution - read from stdin
let input = '';

process.stdin.on('data', (chunk) => {
  input += chunk;
});

process.stdin.on('end', () => {
  try {
    const eventData = JSON.parse(input);
    preToolUse(eventData);
  } catch (error) {
    console.error('Error parsing event data:', error);
    process.exit(1);
  }
});