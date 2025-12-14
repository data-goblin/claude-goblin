# 002: Enhanced Windows Support

## Summary
Improve Windows compatibility for all features, ensuring first-class support alongside macOS and Linux.

## Current State
- Core functionality (parsing, database, stats) should work
- Audio hooks use platform detection but untested on Windows
- Status bar (rumps) is macOS-only
- Path handling may have issues with Windows separators

## Implementation

### Audio Hooks
- Test Windows SAPI integration for TTS
- Verify `winsound` module works for audio notifications
- Add PowerShell fallback for complex audio

### Status Bar Alternative
- Research Windows system tray libraries (pystray, win10toast)
- Implement Windows-native system tray icon
- Show token count in tray tooltip

### Path Handling
- Audit all `os.path` usage for Windows compatibility
- Use `pathlib.Path` consistently
- Handle `~` expansion on Windows

### Testing
- Set up Windows CI runner (GitHub Actions)
- Create Windows-specific test cases
- Document Windows installation steps

## Tasks
- [ ] Audit codebase for Windows path issues
- [ ] Test audio hooks on Windows
- [ ] Implement Windows system tray alternative
- [ ] Add Windows to CI matrix
- [ ] Update documentation with Windows-specific notes
- [ ] Test with Windows Terminal and PowerShell
