import json
import urllib.request
import urllib.error
import time
from .utils import logger

class LLMClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or ""
        self.endpoint = "https://llm.chutes.ai/v1/chat/completions"
        
        # Priority list of models for fallback
        self.models = [
            "Qwen/Qwen3.5-397B-A17B-TEE",
            "Qwen/Qwen3-235B-A22B-Instruct-2507-TEE",
            "Qwen/Qwen3-235B-A22B-Thinking-2507"
        ]
        self.current_model_index = 0

    def _get_current_model(self):
        return self.models[self.current_model_index]

    def _rotate_model(self):
        """Switches to the next model in the priority list."""
        self.current_model_index = (self.current_model_index + 1) % len(self.models)
        logger.warning(f"Switching to fallback model: {self._get_current_model()}")

    def send_prompt(self, system_prompt, user_prompt):
        """Sends a prompt to the LLM and returns the JSON response with fallback support."""
        
        max_retries = len(self.models) * 2 # Allow cycling through list twice
        attempt = 0
        
        while attempt < max_retries:
            current_model = self._get_current_model()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            payload = {
                "model": current_model,
                "messages": messages,
                "stream": False,
                "max_tokens": 4096,
                "temperature": 0.0,
                "response_format": { "type": "json_object" }
            }
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
            
            try:
                with urllib.request.urlopen(req) as response:
                    if response.status != 200:
                        logger.error(f"LLM API Error: Status {response.status}")
                        raise urllib.error.HTTPError(req.full_url, response.status, "API Error", headers, None)
                    
                    body = response.read().decode("utf-8")
                    response_json = json.loads(body)
                    content = response_json["choices"][0]["message"].get("content")
                    
                    if not content:
                        logger.warning(f"LLM {current_model} returned empty content. Retrying with next model...")
                        self._rotate_model()
                        time.sleep(1)
                        attempt += 1
                        continue

                    # Try to extract JSON from markdown block if present
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].strip()
                        
                    return json.loads(content)
                    
            except urllib.error.HTTPError as e:
                if e.code in [404, 429, 503]:
                    logger.warning(f"LLM {current_model} failed with {e.code}. Retrying with next model...")
                    self._rotate_model()
                    time.sleep(1)
                    attempt += 1
                else:
                    logger.error(f"HTTP Error calling LLM: {e.code} - {e.read().decode()}")
                    raise
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"LLM {current_model} returned invalid content: {e}. Retrying with next model...")
                self._rotate_model()
                time.sleep(1)
                attempt += 1
            except Exception as e:
                logger.error(f"Error calling LLM: {str(e)}")
                raise

        raise Exception("All LLM models failed after retries.")

    def generate_text(self, prompt, max_tokens=100, temperature=0.3):
        """Generate simple text without JSON formatting with fallback support."""
        
        max_retries = len(self.models) * 2
        attempt = 0
        
        while attempt < max_retries:
            current_model = self._get_current_model()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            payload = {
                "model": current_model,
                "messages": messages,
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
            
            try:
                with urllib.request.urlopen(req) as response:
                    if response.status != 200:
                         raise urllib.error.HTTPError(req.full_url, response.status, "API Error", headers, None)
                    
                    body = response.read().decode("utf-8")
                    response_json = json.loads(body)
                    content = response_json["choices"][0]["message"].get("content")
                    
                    if not content:
                        logger.warning(f"LLM {current_model} returned empty content. Retrying with next model...")
                        self._rotate_model()
                        time.sleep(1)
                        attempt += 1
                        continue
                    
                    return content.strip()
                    
            except urllib.error.HTTPError as e:
                if e.code in [404, 429, 503]:
                    logger.warning(f"LLM {current_model} failed with {e.code}. Retrying with next model...")
                    self._rotate_model()
                    time.sleep(1)
                    attempt += 1
                else:
                    logger.warning(f"Error in text generation: {str(e)}")
                    raise
            except Exception as e:
                logger.warning(f"Error in text generation: {str(e)}")
                raise

        return ""
