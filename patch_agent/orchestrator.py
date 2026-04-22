import os
import time
import json
from .llm_client import LLMClient
from .agent import PatchAgent
from .utils import logger


class Orchestrator:
    """
    Intelligent orchestration layer that routes user requests appropriately.
    
    Actions:
    - display_to_user: Direct conversational response (greetings, help, etc.)
    - call_patch_agent: Delegate to PatchAgent for bug fixes
    - clarify_request: Ask user for more details
    - out_of_scope: Politely decline requests outside capabilities
    """
    
    def __init__(self, target_dir, api_key=None):
        self.target_dir = os.path.abspath(target_dir)
        self.llm = LLMClient(api_key)
        self.patch_agent = PatchAgent(target_dir, api_key)
        
        # Load schema for prompt
        base_dir = os.path.dirname(__file__)
        with open(os.path.join(base_dir, 'orchestrator_schema.json'), 'r') as f:
            self.schema_str = f.read()
        
        # Conversation history for context
        self.conversation_history = []
    
    def process(self, user_message):
        """
        Main entry point. Process user message and return appropriate response.
        
        Returns:
            dict with keys:
            - action: str (the action taken)
            - response: str (message to display to user, if applicable)
            - patch_success: bool (True/False if patch agent was called, None otherwise)
            - patch_summary: str (summary from patch agent, if applicable)
        """
        logger.info(f"Orchestrator: {user_message[:50]}...")
        
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Classify intent using LLM
        classification = self._classify_intent(user_message)
        
        if not classification:
            # Classification failed after retries - return error instead of defaulting to patch agent
            logger.error("Intent classification failed after all retries")
            return {
                "action": "error",
                "response": "⚠️ I'm experiencing temporary issues (rate limit). Please try again in a few seconds.",
                "patch_success": None,
                "patch_summary": None
            }
        
        action = classification.get("action")
        logger.info(f"Classified as: {action}")
        
        # Execute the appropriate action
        result = self._execute_action(classification, user_message)
        
        # Add response to conversation history
        if result.get("response"):
            self.conversation_history.append({
                "role": "assistant", 
                "content": result["response"]
            })
        
        return result
    
    def _classify_intent(self, user_message):
        """Use LLM to classify user intent and determine action."""
        
        system_prompt = f"""You are an intelligent router for a Patch Agent system. Your job is to analyze user messages and decide the appropriate action.

AVAILABLE ACTIONS:
1. "display_to_user" - For greetings, casual chat, status inquiries, or questions about capabilities
   Examples: "hi", "hello", "how are you", "what can you do?", "thanks"
   
2. "call_patch_agent" - For bug reports, error descriptions, or requests to fix code issues
   Examples: "The app shows a 500 error", "Fix the login bug", "There's a crash on the homepage"
   
3. "clarify_request" - When the request is too vague or missing critical details
   Examples: "fix the bug" (which bug?), "it's broken" (what's broken?)
   
4. "out_of_scope" - For requests completely outside your capabilities (writing poems, unrelated tasks)
   Examples: "Write me a poem", "What's the weather?", "Tell me a joke"

CONTEXT:
- You are a Patch Agent designed to fix bugs in a production log-monitoring web application
- log monitoring web app(running on port 3000) is used to monitor the logs
- You can stop the server, edit code files, install npm packages, and restart the server
- You can install the npm packages/depedencies if user asks to do so
- You can stop and restart the server if user asks to do so
- You CANNOT create new files, delete files, or run arbitrary commands

RESPOND WITH JSON ONLY. STRICT SCHEMA:
{self.schema_str}

Be friendly and helpful in your messages. For greetings, be warm but professional."""

        # Include recent conversation history for context
        history_context = ""
        if len(self.conversation_history) > 1:
            recent = self.conversation_history[-5:]  # Last 5 messages
            history_context = "\n\nRECENT CONVERSATION:\n"
            for msg in recent[:-1]:  # Exclude current message
                history_context += f"{msg['role'].upper()}: {msg['content']}\n"
        
        user_prompt = f"""{history_context}
CURRENT USER MESSAGE:
{user_message}

Classify this message and provide the appropriate action and response."""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.llm.send_prompt(system_prompt, user_prompt)
                
                # Validate required fields
                if "action" not in response:
                    logger.error("LLM response missing 'action' field")
                    return None
                
                # Defensive normalization: if LLM returned schema structure instead of value
                # e.g., {"const": "display_to_user"} instead of "display_to_user"
                action = response.get("action")
                if isinstance(action, dict) and "const" in action:
                    logger.warning(f"LLM returned schema structure for action, normalizing: {action}")
                    response["action"] = action["const"]
                
                return response
                
            except Exception as e:
                logger.error(f"Intent classification failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        # All retries exhausted
        return None
    
    def _execute_action(self, classification, original_message):
        """Execute the classified action and return result."""
        
        action = classification.get("action")
        
        if action == "display_to_user":
            return {
                "action": "display_to_user",
                "response": classification.get("message", "Hello! How can I help you today?"),
                "patch_success": None,
                "patch_summary": None
            }
        
        elif action == "call_patch_agent":
            # Use the refined bug description or original message
            bug_description = classification.get("bug_description", original_message)
            return self._call_patch_agent(bug_description)
        
        elif action == "clarify_request":
            return {
                "action": "clarify_request",
                "response": classification.get("message", "Could you please provide more details about the issue?"),
                "patch_success": None,
                "patch_summary": None
            }
        
        elif action == "out_of_scope":
            return {
                "action": "out_of_scope",
                "response": classification.get("message", "I apologize, but that request is outside my capabilities. I'm designed to help fix bugs in the web application."),
                "patch_success": None,
                "patch_summary": None
            }
        
        else:
            # Unknown action, default to patch agent
            logger.warning(f"Unknown action '{action}', defaulting to patch agent")
            return self._call_patch_agent(original_message)
    
    def _call_patch_agent(self, bug_description):
        """Delegate to patch agent and return result."""
        
        logger.info("Orchestrator: Routing to Patch Agent...")
        time.sleep(2)
        
        try:
            success = self.patch_agent.run(bug_description)
            
            if success:
                summary = self.patch_agent.last_fix_summary or "Bug fix applied successfully."
                return {
                    "action": "call_patch_agent",
                    "response": f"✅ {summary}",
                    "patch_success": True,
                    "patch_summary": summary
                }
            else:
                return {
                    "action": "call_patch_agent", 
                    "response": "❌ Failed to apply the fix. Check the logs for details.",
                    "patch_success": False,
                    "patch_summary": None
                }
                
        except Exception as e:
            logger.error(f"Patch agent failed with exception: {e}")
            return {
                "action": "call_patch_agent",
                "response": f"❌ Error: {str(e)}",
                "patch_success": False,
                "patch_summary": None
            }
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
        logger.info("Conversation history cleared")
    
    @property
    def last_fix_summary(self):
        """Proxy to patch agent's last fix summary for backwards compatibility."""
        return self.patch_agent.last_fix_summary
