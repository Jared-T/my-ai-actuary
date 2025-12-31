I'll start by exploring the codebase to understand the existing structure and then continue implementing the project context injection feature.

🔧 Tool: Glob
Input: {
  "pattern": "**/*.{ts,tsx,js,jsx}"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/package.json"
}

Let me search for source files specifically in the src directory, excluding node_modules:

🔧 Tool: Glob
Input: {
  "pattern": "src/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "app/**/*.{ts,tsx}"
}

🔧 Tool: Bash
Input: {
  "command": "ls -la /Users/jared/Documents/FynbosAI/Products/my-ai-actuary/",
  "description": "List root directory contents"
}

Now let me explore the project structure more thoroughly to understand the codebase, particularly focusing on the components, lib, backend directories, and any existing context/session management:

🔧 Tool: Glob
Input: {
  "pattern": "components/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "lib/**/*.{ts,tsx}"
}

🔧 Tool: Glob
Input: {
  "pattern": "backend/**/*.{ts,tsx,py}"
}

🔧 Tool: Read
Input: {
  "file_path": "/Users/jared/Documents/FynbosAI/Products/my-ai-actuary/CLAUDE.md"
}
