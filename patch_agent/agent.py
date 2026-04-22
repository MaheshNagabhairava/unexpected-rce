import os
import json
import time
from .llm_client import LLMClient
from .validator import Validator
from .executor import Executor
from .security_reviewer import SecurityReviewer
from .utils import logger, list_files_recursive, read_file

class PatchAgent:
    def __init__(self, target_dir, api_key=None):
        self.target_dir = os.path.abspath(target_dir)
        self.llm = LLMClient(api_key)
        self.validator = Validator(self.target_dir)
        self.security_reviewer = SecurityReviewer(self.target_dir, api_key)
        self.executor = Executor(self.target_dir)
        self.last_fix_summary = None  # Store summary for web interfacee
        
        # Load schema for prompt
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, 'schema.json'), 'r') as f:
            self.schema_str = f.read()

    def run(self, user_bug_report, max_retries=3):
        logger.info(f"Agent starting for bug: {user_bug_report}")
        
        # 1. Gather Context
        logger.info("Patch Agent: Reading source repo...")
        context = self._gather_context()
        
        # 2. Construct Prompt
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(user_bug_report, context)

        # 3. LLM Loop
        retries = 0
        while retries < max_retries:
            logger.info(f"Patch Agent: Attempt {retries+1} checking with LLM for inputs...")
            
            # --- DEBUG LOGGING START ---
            print("\n" + "="*40)
            print(">>> SENDING TO LLM >>>")
            print(f"SYSTEM PROMPT:\n{system_prompt}\n")
            print(f"USER PROMPT:\n{user_prompt}")
            print("="*40 + "\n")
            # --- DEBUG LOGGING END ---
            
            time.sleep(2) # Delay for better UI experience
            logger.info("Patch Agent: Planning...")
            time.sleep(1) # Delay for better UI experience
            try:
                response_json = self.llm.send_prompt(system_prompt, user_prompt)
            except Exception as e:
                logger.error(f"LLM Call failed: {e}")
                return False

            logger.info("Received response from LLM. Validating...")
            
            # --- DEBUG LOGGING START ---
            print("\n" + "="*40)
            print("<<< RECEIVED FROM LLM <<<")
            print(json.dumps(response_json, indent=2))
            print("="*40 + "\n")
            # --- DEBUG LOGGING END ---

            # 4. Validate
            is_valid, error_msg = self.validator.validate(response_json)
            
            if is_valid:
                # Check if there are any code_edit actions
                has_code_edits = any(action.get("type") == "code_edit" for action in response_json.get("actions", []))
                
                if has_code_edits:
                    logger.info("Patch Agent: Plan Validated. Routing to security agent for review...")
                    time.sleep(2)  # Delay for better UI experience
                    
                    # 5. Security Review (CRITICAL STEP)
                    # Only provide context of files being modified, not entire repo
                    modified_context = self.security_reviewer.gather_modified_files_context(response_json["actions"])
                    security_approved, security_result, security_error = self.security_reviewer.review_changes(
                        response_json["actions"],
                        full_context=modified_context
                    )
                    
                    if not security_approved:
                        logger.error(f"Security Review FAILED: {security_error}")
                        # Security failures are CRITICAL - abort immediately
                        return False
                    
                    logger.info("Security Review PASSED. Executing...")
                    time.sleep(2)  # Delay for better UI experience
                else:
                    logger.info("Patch Agent: No code changes to review. Skipping security review...")
                
                time.sleep(2)  # Delay before execution
                try:
                    self.executor.execute_actions(response_json["actions"])
                    
                    # Generate AI summary from ALL action reasons
                    reasons = []
                    for action in response_json.get("actions", []):
                        action_type = action.get("type")
                        if action_type == "code_edit":
                            # code_edit has reason inside the "edit" object
                            reason = action.get("edit", {}).get("reason")
                        else:
                            # stop_server, restart_server, npm_install have top-level "reason"
                            reason = action.get("reason")
                        if reason:
                            reasons.append(reason)
                    
                    if reasons:
                        summary = self._generate_fix_summary(reasons)
                        self.last_fix_summary = summary  # Store for web interface
                        logger.info(f"Patch Agent: Bug fix or action completed successfully. {summary}")
                    else:
                        self.last_fix_summary = None
                        logger.info("Patch Agent: Bug fix or action completed successfully.")
                    
                    return True
                except Exception as e:
                    logger.error(f"Execution failed: {e}")
                    # In a real agent, we might feed this back. For now, strict 'Exec->Done' or fail.
                    return False
            else:
                # Critical Security Check: Abort immediately on suspicious removal or blocklist violation
                if "Suspicious code removal" in error_msg or "Security Violation" in error_msg:
                    logger.error(f"Critical Validation Failure: {error_msg}. Aborting immediately.")
                    return False

                logger.warning(f"Validation Failed: {error_msg}")
                # Feedback loop
                user_prompt += f"\n\nPrevious proposal was rejected by strict validator:\n{json.dumps(response_json, indent=2)}\n\nError: {error_msg}\n\nPlease correct your proposal strictly following the schema and rules."
                retries += 1
                
        logger.error("Max retries reached. Agent failed to generate valid plan.")
        return False

    def _gather_context(self):
        # Read all source files in target dir
        files = list_files_recursive(self.target_dir)
        context_str = "RELAVENT SOURCE CODE:\n"
        
        for f in files:
            try:
                rel_path = os.path.relpath(f, self.target_dir)
                # Skip large assets, binary files, and lock files
                if f.endswith(('.png', '.pyc', '.git', '.zip', '.log', 'package-lock.json')):
                    continue
                    
                content = read_file(f, max_lines=300) # Limit lines
                context_str += f"\n--- {rel_path} ---\n{content}\n"
            except Exception as e:
                logger.warning(f"Could not read {f}: {e}")
                
        return context_str

    def _build_system_prompt(self):
        return f"""You are the 'Patch Agent'. Your goal is to fix bugs in a live production web application safely which is running on port 3000.
        
SYSTEM GOAL:
Fix the bug exactly as requested by user. Do not refactor, reformat, or touch unrelated code. Minimum change.

ALLOWED ACTIONS:
- stop_server (To stop the server)
- code_edit (max 20 lines, exact snippet match)
- npm_install (To install dependencies/packages)
- restart_server (To restart the server)

You CANNOT run arbitrary commands.
You are not allowed to create a file or directory.
You are not allowed to delete the production app files.
You MUST stop the server before editing code or installing dependencies/libraries with npm. You MUST restart the server after finishing.
If you only stop_server and restart_server without code_edit, then give the reason as "stopped server or restarted server as per user request".

OUTPUT JSON ONLY. STRICT SCHEMA:
{self.schema_str}
"""

    def _build_user_prompt(self, bug_report, context):
        return f"""USER PROMPT:
{bug_report}

CURRENT APP CODE:
{context}

Analyze the user prompt and propose fixes using ONLY the allowed actions in your JSON output.
"""

    def _generate_fix_summary(self, reasons):
        """Generate a concise summary of what was fixed/actions taken using LLM."""
        try:
            reasons_text = "\n".join(f"- {reason}" for reason in reasons if reason != "N/A")
            
            prompt = f"""You are a helpful assistant summarizing code changes. 
Given the following list of changes made to fix a bug, create ONE concise sentence (maximum 15 words) that summarizes what was accomplished.

Changes made:
{reasons_text}
If you only stop_server and restart_server without code_edit, then give the summary as "server stopped or restarted as per user request"
Provide ONLY the summary sentence, nothing else. Start with a verb like "Changed", "Updated", "Fixed", "Modified", "Stopped", "Restarted", etc."""

            try:
                # Use the generate_text method
                summary = self.llm.generate_text(prompt, max_tokens=50, temperature=0.3)
                return summary if summary else "Code changes applied."
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
                return "Code changes applied."
                
        except Exception as e:
            logger.warning(f"Error in summary generation: {e}")
            return "Code changes applied."
