import os
import json
from .utils import logger, read_file

class Validator:
    def __init__(self, working_directory):
        self.working_directory = working_directory
        self.allowed_actions = {"stop_server", "code_edit", "npm_install", "restart_server"}
        # Whitelist for npm packages - only these can be installed (any version allowed)
        self.allowed_npm_packages = {"react", "react-dom", "next"}
        # self.allowed_delete_paths removed

    def validate(self, original_response):
        """Validates the LLM response object. Returns (True, None) or (False, error_message)."""
        
        # 1. Structure Check
        if not isinstance(original_response, dict) or "actions" not in original_response:
            return False, "Response must be a JSON object with an 'actions' array."
        
        actions = original_response["actions"]
        if not isinstance(actions, list):
            return False, "'actions' must be a list."

        # 2. Logic & Limits
        if not actions:
            return False, "Action list cannot be empty."

        edited_files = set()
        has_stop = False
        has_edit = False
        has_restart = False
        
        for i, action in enumerate(actions):
            action_type = action.get("type")
            
            if action_type not in self.allowed_actions:
                return False, f"Unknown action type: {action_type}"
            
            # Order checks
            if action_type == "stop_server":
                has_stop = True
                if has_edit:
                    return False, "stop_server must appear BEFORE code_edit."
            
            if action_type in ["code_edit", "npm_install"]:
                if not has_stop:
                    return False, f"stop_server must be called BEFORE {action_type}."
                
                if action_type == "code_edit":
                    has_edit = True
                    if has_restart:
                        return False, "code_edit must appear BEFORE restart_server."
                    
                    # Check specific edit rules
                    valid, err = self._validate_edit(action)
                    if not valid:
                        return False, err
                    
                    edited_files.add(action["file"])
                
                elif action_type == "npm_install":
                    # Validate npm packages against whitelist
                    valid, err = self._validate_npm_install(action)
                    if not valid:
                        return False, err
                
            if action_type == "restart_server":
                has_restart = True
                if has_edit and not has_stop: # This implies we didn't stop? No, has_stop is checked above.
                     pass # Valid.

        
        if len(edited_files) > 3:
            return False, f"Too many files edited. Maximum is 3."
            #Too many files edited ({len(edited_files)}). Maximum is 3.
            
        return True, None

    def _validate_edit(self, edit_action):
        """Validates a specific code_edit action."""
        file_path = edit_action.get("file")
        if not file_path:
             return False, "code_edit missing 'file'."
             
        # Resolve path
        full_path = os.path.abspath(os.path.join(self.working_directory, file_path))
        
        # Security check: Prevent path traversal attacks
        # Ensure the resolved path is within the working directory
        working_dir_normalized = os.path.abspath(self.working_directory)
        if not full_path.startswith(working_dir_normalized + os.sep) and full_path != working_dir_normalized:
            return False, f"Security violation: File path escapes working directory"
        
        # Additional restriction: Only allow modifications within the 'app' folder
        app_folder = os.path.join(working_dir_normalized, "app")
        if not full_path.startswith(app_folder + os.sep) and full_path != app_folder:
            return False, f"Security violation: File modifications restricted to defined folder only"
        
        if not os.path.exists(full_path):
            return False, f"File does not exist"
            
        edit = edit_action.get("edit")
        if not edit:
             return False, "code_edit missing 'edit' object."
             
        # Check snippet length (approximate via new lines in new_snippet)
        new_snippet = edit.get("new_snippet", "")
        if new_snippet.count('\n') > 20: # Strict 20 lines
             return False, "Edit 'new_snippet' exceeds 20 lines."
             
        # Check original snippet matches
        original_snippet = edit.get("original_snippet", "")
        try:
            file_content = read_file(full_path)
            # Normalize line endings for comparison importance?
            # Start simple: exact string check
            if original_snippet not in file_content:
                # Fallback: check with standardized newlines?
                if original_snippet.replace('\r\n', '\n') not in file_content.replace('\r\n', '\n'):
                    return False, f"original_snippet not found. Edit rejected."
                    #original_snippet not found in {file_path}. Edit rejected.
                    
            # --- SECURITY BLOCKLIST CHECK ---
            # Prevent adding code that performs file creation or process execution
            prohibited_patterns = [
                # Node.js
                "fs.write", "fs.create", "fs.unlink", "fs.rm", "child_process", "exec(", "spawn(", 
                "require('fs')", 'require("fs")', "import fs",
                "from 'fs'", 'from "fs"', # ESM named imports
                "writeFileSync", "writeFile", "createWriteStream", # Naked functions if imported
                # Python
                "os.system", "subprocess", "open(", "os.remove", "os.unlink", "shutil.rmtree"
            ]
            
            new_snippet = edit.get("new_snippet", "")
            
            for pattern in prohibited_patterns:
                # Only block if it's NEWLY added (not present in original)
                if pattern in new_snippet and pattern not in original_snippet:
                     return False, f"Security Violation: Proposed edit looks like suspicious pattern '{pattern}'. Aborted safely."
                     # Security Violation: Proposed edit contains prohibited pattern '{pattern}'. File creation and system calls are restricted
            
            # --- ANTI-GUTTING CHECK (Entropy) ---
            # Only reject large-scale code removal (original > 10 lines)
            original_line_count = original_snippet.count('\n') + 1
            if original_line_count > 10 and len(original_snippet) > 50 and len(new_snippet) < (0.2 * len(original_snippet)):
                return False, "Suspicious code removal detected: Rejected to prevent functional deletion."

            # --- SEMANTIC CHECK (No Comment Replacements) ---
            stripped_new = new_snippet.strip()
            
            # Check if replacement is purely comments (// or /* or *)
            def is_only_comments_or_whitespace(snippet):
                """Check if a code snippet contains only comments and whitespace."""
                lines = snippet.strip().splitlines()
                for line in lines:
                    l = line.strip()
                    if not l:  # Empty line
                        continue
                    # Check if line is a comment
                    if not (l.startswith('//') or l.startswith('/*') or l.startswith('*') or l.endswith('*/')):
                        return False  # Found non-comment code
                return True  # All lines are comments or whitespace
            
            # Only block empty/comment-only replacements if original is > 10 lines
            # Small removals (<=10 lines) are allowed for genuine unused code cleanup
            if not stripped_new or is_only_comments_or_whitespace(new_snippet):
                if original_line_count > 10:
                    original_is_only_comments = is_only_comments_or_whitespace(original_snippet)
                    if not stripped_new and not original_is_only_comments:
                        return False, "New snippet cannot be empty (original code is > 10 lines)."
                    if stripped_new and not original_is_only_comments:
                        return False, "Security Violation: It is interpreted as functional deletion. Aborted the operation safely."
                # If original <= 10 lines, allow the removal (genuine small cleanup)

        except Exception as e:
            return False, f"Error reading file {file_path}: {e}"
            
        return True, None

    def _validate_npm_install(self, install_action):
        """Validates an npm_install action against package whitelist."""
        packages = install_action.get("packages", [])
        
        if not packages:
            return False, "npm_install missing 'packages' array."
        
        if not isinstance(packages, list):
            return False, "npm_install 'packages' must be an array."
        
        rejected_packages = []
        for pkg in packages:
            # Strip version specifier (e.g., "react@18.2.0" -> "react")
            # Handles: react, react@18, react@^18.0.0, react@latest, @scope/pkg@1.0
            if '@' in pkg:
                # Handle scoped packages like @types/react
                if pkg.startswith('@'):
                    # Scoped package: @scope/name@version
                    parts = pkg.split('/')
                    if len(parts) > 1 and '@' in parts[1]:
                        # @scope/name@version -> @scope/name
                        pkg_name = parts[0] + '/' + parts[1].split('@')[0]
                    else:
                        pkg_name = pkg
                else:
                    # Regular package with version: name@version -> name
                    pkg_name = pkg.split('@')[0]
            else:
                pkg_name = pkg
            
            if pkg_name not in self.allowed_npm_packages:
                rejected_packages.append(pkg)
        
        if rejected_packages:
            return False, f"Patch Agent: Security Violation: Package(s) not in whitelist: {', '.join(rejected_packages)}."
        
        return True, None
