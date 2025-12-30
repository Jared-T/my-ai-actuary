# Releases

Version history for openai-agents-python (key releases).

## v0.6.1 (Latest)
**Published:** 2025-11-20

- Fix: invalid model setting when passing prompt to Agent
- Fix: default settings for SIP realtime runner
- Docs: document input guardrail execution modes

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.6.0...v0.6.1

---

## v0.6.0 (Breaking Changes)
**Published:** 2025-11-18

### Breaking Change
**Handoff behavior changed**: Message history is now collapsed into a single message when handing off to a new agent. Test before upgrading.

### Key Changes
- Nest handoff history by default
- Upgrade openai-python to 2.8.0 for GPT 5.1
- Add `prompt_cache_retention` to ModelSettings
- Add `run_in_parallel` parameter to input guardrails
- Fix agent memory leak using weakref
- Add tool error logging

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.5.1...v0.6.0

---

## v0.5.1
**Published:** 2025-11-13

Key update: Support for new tools from the GPT-5.1 launch: `shell` and `apply_patch`.

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.5.0...v0.5.1

---

## v0.5.0
**Published:** 2025-11-05

### Key Changes
- Added support for `RealtimeRunner` to handle SIP protocol connections
- Significantly revised internal logic of `Runner#run_sync` for Python 3.14 compatibility
- Add per-request usage data to Usage
- Add Dapr session storage option

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.4.2...v0.5.0

---

## v0.4.0 (Breaking Changes)
**Published:** 2025-10-17

### Breaking Change
**openai package v1.x versions are no longer supported**. Use openai v2.x with this SDK.

### Key Changes
- Migrate openai from 1.x to 2.2.0
- Add MCP message handler configuration
- Support image/file output types for functions
- Add graceful cancel mode for streaming runs
- Roll back session changes when Guardrail tripwire is triggered

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.3.3...v0.4.0

---

## v0.3.0
**Published:** 2025-09-11

### Key Changes
- New realtime updates based on the GA Realtime API
- Save session on turn rather than at final response
- Allow passing both session and input list

**Full Changelog**: https://github.com/openai/openai-agents-python/compare/v0.2.11...v0.3.0

---

## Summary of Breaking Changes

| Version | Breaking Change |
|---------|----------------|
| v0.6.0 | Handoff message history collapsed to single message |
| v0.4.0 | openai v1.x no longer supported, requires v2.x |

## Upgrade Path

1. **v0.5.x → v0.6.x**: Test handoff behavior thoroughly before upgrading
2. **v0.3.x → v0.4.x**: Update openai package to v2.x first
3. **v0.2.x → v0.3.x**: Review realtime API changes if using voice features
