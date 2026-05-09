**Unexpected code execution(RCE):**

Agentic systems - including popular vibe coding tools - often generate and execute code. Attackers exploit
code-generation features or embedded tool access to escalate actions into remote code execution (RCE),
local misuse, or exploitation of internal systems. Because this code is often generated in real-time by the
agent it can bypass traditional security controls.
Prompt injection, tool misuse, or unsafe serialization can convert text into unintended executable behavior.
While code execution can be triggered via the same tool interfaces discussed under ASI02, ASI05 focuses
on unexpected or adversarial execution of code (scripts, binaries, JIT/WASM modules, deserialized
objects, template engines, in memory evaluations) that leads to host or container compromise, persistence,
or sandbox escape - outcomes that require host and runtime-specific mitigations beyond ordinary tool-use
controls.
This entry builds on LLM01:2025 Prompt Injection and LLM05:2025 Improper Output Handling, reflecting
their evolution in agentic systems from a single manipulated output interpreted or executed to orchestrated
multi-tool chains that achieve execution through a sequence of otherwise legitimate tool calls.

**Lab Workflow:**
<img width="981" height="501" alt="Image" src="https://github.com/user-attachments/assets/761af795-25d4-4afa-ad21-320ed88cdbf8" />

