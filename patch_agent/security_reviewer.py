import os
import json
from .llm_client import LLMClient
from .utils import logger, list_files_recursive, read_file


class SecurityReviewer:
    """
    LLM-based security reviewer that analyzes proposed code changes for vulnerabilities.
    Acts as a defense layer against malicious or insecure patches.
    """
    
    def __init__(self, working_directory, api_key=None):
        self.working_directory = working_directory
        self.llm = LLMClient(api_key)
        
        # Load security review schema
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, 'security_review_schema.json'), 'r') as f:
            self.schema_str = f.read()
    
    def review_changes(self, proposed_actions, full_context=None):
        """
        Review proposed code changes for security vulnerabilities.
        
        Args:
            proposed_actions: List of actions from the patch agent
            full_context: Full application code context (optional)
        
        Returns:
            (approved: bool, review_result: dict, error_msg: str or None)
        """
        logger.info("Security Reviewer Agent: Starting security review of proposed changes...")
        
        # Build the security review prompt
        system_prompt = self._build_security_review_prompt()
        user_prompt = self._build_user_review_prompt(proposed_actions, full_context)
        
        # --- DEBUG LOGGING START ---
        import sys
        print("\n" + "="*60, flush=True)
        print(">>> SECURITY REVIEW: SENDING TO LLM >>>", flush=True)
        print(f"SYSTEM PROMPT:\n{system_prompt}\n", flush=True)
        print(f"USER PROMPT:\n{user_prompt}", flush=True)
        print("="*60 + "\n", flush=True)
        sys.stdout.flush()
        # --- DEBUG LOGGING END ---
        
        # Call LLM for security analysis with retry on invalid format
        max_review_retries = 3
        review_result = None
        
        for review_attempt in range(max_review_retries):
            try:
                review_result = self.llm.send_prompt(system_prompt, user_prompt)
            except Exception as e:
                logger.error(f"Security review LLM call failed: {e}")
                return False, None, f"Security review failed: {e}"
            
            # --- DEBUG LOGGING START ---
            print("\n" + "="*60, flush=True)
            print("<<< SECURITY REVIEW: RECEIVED FROM LLM <<<", flush=True)
            print(json.dumps(review_result, indent=2), flush=True)
            print("="*60 + "\n", flush=True)
            sys.stdout.flush()
            # --- DEBUG LOGGING END ---
            
            # Attempt to normalize malformed response (e.g., LLM returned schema instead of values)
            review_result = self._normalize_review_response(review_result)
            
            # Validate the response structure
            if self._validate_review_response(review_result):
                break  # Valid response, proceed
            
            if review_attempt < max_review_retries - 1:
                logger.warning(f"Invalid security review format (attempt {review_attempt + 1}/{max_review_retries}). Retrying...")
                # Add feedback to the prompt so the LLM corrects itself
                user_prompt += f"\n\nYour previous response was INVALID. You returned:\n{json.dumps(review_result, indent=2)}\n\nERROR: The response must have 'approved' as a boolean (true/false), 'risk_level' as a string, and 'findings' as an array. Do NOT return the JSON schema definition. Return actual VALUES. Example: {{\"approved\": true, \"risk_level\": \"SAFE\", \"findings\": [], \"summary\": \"...\"}}"
            else:
                logger.error("Security review failed after all retries: invalid response format")
                return False, None, "Invalid security review response format after multiple retries"
        
        # Check approval status
        approved = review_result.get("approved", False)
        risk_level = review_result.get("risk_level", "UNKNOWN")
        findings = review_result.get("findings", [])
        
        if not approved:
            # Build detailed error message
            error_msg = f"Security Review REJECTED ({risk_level} risk):\n"
            for finding in findings:
                error_msg += f"  - [{finding['severity']}] {finding['category']}: {finding['description']}\n"
                error_msg += f"    Location: {finding['location']}\n"
                if 'recommendation' in finding:
                    error_msg += f"    Fix: {finding['recommendation']}\n"
            
            logger.warning(f"Security Reviewer Agent: Security review failed:\n{error_msg}")
            return False, review_result, error_msg
        
        # Log approval
        if findings:
            logger.info(f"Security Reviewer Agent: Security review APPROVED with {len(findings)} non-blocking findings ({risk_level} risk)")
        else:
            logger.info(f"Security Reviewer Agent: Security review APPROVED ({risk_level} risk)")
        
        return True, review_result, None
    
    def _build_security_review_prompt(self):
        """Build the system prompt for security review"""
        return f"""You are a SECURITY EXPERT reviewing proposed code changes for a production web application.

YOUR MISSION:
Detect and flag ANY security vulnerabilities, malicious code, or risky patterns in the proposed changes.

CRITICAL SECURITY CHECKS:
1. **XSS (Cross-Site Scripting)**: Unescaped user input in HTML/JavaScript
2. **SQL Injection**: Unsanitized input in database queries
3. **Command Injection**: User input passed to system commands, exec(), eval()
4. **SSRF (Server-Side Request Forgery)**: User-controlled URLs in fetch/http requests
5. **Data Exfiltration**: Unauthorized data transmission to external endpoints
6. **Path Traversal**: File operations with user-controllable paths
7. **Unsafe Deserialization**: Deserializing untrusted data
8. **Hardcoded Secrets**: API keys, passwords, tokens in code
9. **Authentication Bypass**: Removing or weakening auth checks
10. **Insecure Randomness**: Using weak random for security-critical operations

APPROVAL CRITERIA:
- APPROVE (safe to execute) if changes are secure or have LOW risk
- REJECT if ANY HIGH or CRITICAL vulnerabilities are found
- REJECT if code appears intentionally malicious

RESPONSE FORMAT (STRICT JSON):
{self.schema_str}

BE EXTREMELY THOROUGH. When in doubt, REJECT.
"""

    def _build_user_review_prompt(self, proposed_actions, full_context):
        """Build the user prompt with code changes to review"""
        prompt = "PROPOSED CODE CHANGES TO REVIEW:\n\n"
        prompt += "IMPORTANT: Review ONLY the NEW CODE snippets below for security vulnerabilities.\n"
        prompt += "The full repository context is provided for reference only - do NOT flag issues in existing code.\n\n"
        
        # Extract code_edit actions
        for i, action in enumerate(proposed_actions):
            if action.get("type") == "code_edit":
                file_path = action.get("file", "unknown")
                edit = action.get("edit", {})
                original = edit.get("original_snippet", "")
                new_snippet = edit.get("new_snippet", "")
                
                prompt += f"--- Change #{i+1}: {file_path} ---\n"
                prompt += f"ORIGINAL CODE (for context):\n{original}\n\n"
                prompt += f"NEW CODE (REVIEW THIS FOR VULNERABILITIES):\n{new_snippet}\n\n"
                prompt += f"REASON: {action.get('reason', 'Not specified')}\n\n"
        
        # Add limited context - only files being modified
        if full_context:
            prompt += "\nFILE CONTEXT (existing code in modified files, for reference only):\n"
            prompt += full_context
        
        prompt += "\n\nAnalyze ONLY the NEW CODE snippets for security vulnerabilities. Return your findings as JSON."
        
        return prompt
    
    def _normalize_review_response(self, response):
        """
        Attempt to fix common LLM response format issues.
        Handles cases where the LLM returns the JSON schema structure instead of actual values,
        e.g., wrapping values inside a 'properties' key or returning {"const": true} instead of true.
        """
        if not isinstance(response, dict):
            return response
        
        # Case 1: LLM returned schema wrapper with "properties" containing actual values
        if "properties" in response and "approved" not in response:
            props = response["properties"]
            if isinstance(props, dict):
                logger.warning("LLM returned schema-wrapped response. Extracting values from 'properties'...")
                response = props
        
        # Case 2: Values wrapped in schema-like {"const": value} format
        for field in ["approved", "risk_level"]:
            val = response.get(field)
            if isinstance(val, dict) and "const" in val:
                logger.warning(f"Normalizing schema-wrapped field '{field}': {val}")
                response[field] = val["const"]
        
        # Case 3: approved is a string "true"/"false" instead of boolean
        if isinstance(response.get("approved"), str):
            response["approved"] = response["approved"].lower() == "true"
        
        return response
    
    def _validate_review_response(self, response):
        """Validate that the review response has required fields"""
        if not isinstance(response, dict):
            return False
        
        required_fields = ["approved", "risk_level", "findings"]
        for field in required_fields:
            if field not in response:
                logger.error(f"Missing required field in security review: {field}")
                return False
        
        # Validate risk_level enum
        valid_risk_levels = ["SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
        if response["risk_level"] not in valid_risk_levels:
            logger.error(f"Invalid risk_level: {response['risk_level']}")
            return False
        
        return True
    
    def gather_modified_files_context(self, proposed_actions):
        """
        Gather context only for files being modified.
        This provides surrounding code for analysis without auditing the entire repo.
        """
        modified_files = set()
        
        # Extract files being modified
        for action in proposed_actions:
            if action.get("type") == "code_edit":
                file_path = action.get("file", "")
                if file_path:
                    full_path = os.path.join(self.working_directory, file_path)
                    modified_files.add(full_path)
        
        context_str = "FILES BEING MODIFIED (for context):\n"
        
        for file_path in modified_files:
            try:
                rel_path = os.path.relpath(file_path, self.working_directory)
                
                if os.path.exists(file_path):
                    content = read_file(file_path, max_lines=200)  # Limited context
                    context_str += f"\n--- {rel_path} ---\n{content}\n"
            except Exception as e:
                logger.warning(f"Could not read {file_path}: {e}")
        
        return context_str
