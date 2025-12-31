I'll review the previous context and continue implementing the policy guardrails feature. Let me first explore the codebase to understand the existing structure and see what has already been implemented.

🔧 Tool: Glob
Input: {
  "pattern": "**/*.{ts,tsx,py}"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/README.md"
}

Let me search for source files excluding node_modules:

🔧 Tool: Glob
Input: {
  "pattern": "src/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "app/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "components/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "lib/**/*.{ts,tsx}"
}

Let me also check for existing governance-related files and search for any guardrails implementation:

🔧 Tool: Grep
Input: {
  "pattern": "guardrail|governance|policy",
  "-i": true
}

🔧 Tool: Glob
Input: {
  "pattern": "**/governance/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "**/guardrail*/**/*.{ts,tsx}"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/app/page.tsx"
}

There's already a backend with guardrails. Let me examine the existing guardrails implementation: