from flask import Flask, render_template, request, jsonify, Response
import json
import threading
import queue
from datetime import datetime
from patch_agent.orchestrator import Orchestrator

app = Flask(__name__)

# Configuration
TARGET_DIR = "./vulnerable-next-js-poc-main"
orchestrator = Orchestrator(TARGET_DIR)

# Store chat history
chat_history = []
message_queue = queue.Queue()


@app.route('/')
def index():
    """Render the main chat interface"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    user_message = data.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400
    
    # Add user message to history
    user_entry = {
        'type': 'user',
        'message': user_message,
        'timestamp': datetime.now().isoformat()
    }
    chat_history.append(user_entry)
    
    # Process in background thread
    def process_request():
        import logging
        
        agent_entry = {
            'type': 'agent',
            'status': 'processing',
            'message': 'Starting...',
            'timestamp': datetime.now().isoformat(),
            'logs': []
        }
        chat_history.append(agent_entry)
        
        # Define important log messages to show
        important_keywords = [
            'Orchestrator',
            'Classified as',
            'Orchestrator: Routing to Patch Agent',
            'Patch Agent: Reading source repo...',
            'Patch Agent: Planning...',
            'Patch Agent: checking with LLM...',
            'Patch Agent: Plan Validated. Routing to security agent for review...',
            'Security Reviewer Agent: Starting security review of proposed changes...',
            'Security Reviewer Agent: review APPROVED',
            'Security Reviewer Agent: review REJECTED',
            'Security Reviewer Agent: Security review failed',
            'Patch Agent: No code changes to review. Skipping security review',
            'Patch Agent: Security Violation: Package(s) not in whitelist',
            'Patch Agent: Starting execution',
            'Executing:',
            'Patch Agent: Bug fix or action completed successfully.',
            'successfully.',  # Catch the summary sentence
            'failed',
            'error'
            'ERROR'
        ]
        
        # Custom logging handler to capture only important logs
        class FilteredLogHandler(logging.Handler):
            def emit(self, record):
                if record.name == 'PatchAgent':
                    log_message = record.getMessage()
                    
                    # Check if this log contains important keywords
                    if any(keyword.lower() in log_message.lower() for keyword in important_keywords):
                        formatted_message = f"{record.levelname} - {log_message}"
                        agent_entry['logs'].append({
                            'level': record.levelname,
                            'message': formatted_message,
                            'timestamp': datetime.now().isoformat()
                        })
                        # Update main message to latest important log
                        agent_entry['message'] = formatted_message
        
        # Add our custom handler
        log_handler = FilteredLogHandler()
        patch_agent_logger = logging.getLogger('PatchAgent')
        patch_agent_logger.addHandler(log_handler)
        
        try:
            # Process through orchestrator
            result = orchestrator.process(user_message)
            action = result.get('action', 'unknown')
            
            if action == 'display_to_user':
                # Direct conversational response - no success badge needed
                agent_entry['status'] = 'chat'
                agent_entry['message'] = result.get('response', 'Hello!')
            
            elif action == 'call_patch_agent':
                # Patch agent was invoked
                if result.get('patch_success'):
                    agent_entry['status'] = 'chat'  # No badge for successful fixes
                    agent_entry['message'] = result.get('response', '✅ Successfully applied the fix!')
                else:
                    agent_entry['status'] = 'failed'
                    agent_entry['message'] = result.get('response', '❌ Failed to apply the fix.')
            
            elif action == 'clarify_request':
                # Need more info from user - no success badge needed
                agent_entry['status'] = 'chat'
                agent_entry['message'] = result.get('response', 'Could you provide more details?')
            
            elif action == 'out_of_scope':
                # Request outside capabilities - no success badge needed
                agent_entry['status'] = 'chat'
                agent_entry['message'] = result.get('response', 'Sorry, that request is outside my capabilities.')
            
            else:
                # Unknown action
                agent_entry['status'] = 'failed'
                agent_entry['message'] = f'Unknown action: {action}'
                
        except Exception as e:
            agent_entry['status'] = 'failed'
            agent_entry['message'] = f'❌ Error: {str(e)}'
            agent_entry['logs'].append({
                'level': 'ERROR',
                'message': f'ERROR - Exception: {str(e)}',
                'timestamp': datetime.now().isoformat()
            })
        finally:
            # Remove the handler
            patch_agent_logger.removeHandler(log_handler)
    
    thread = threading.Thread(target=process_request)
    thread.start()
    
    return jsonify({'success': True})


@app.route('/api/history')
def get_history():
    """Get chat history"""
    return jsonify({'history': chat_history})


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """Clear chat history"""
    chat_history.clear()
    orchestrator.clear_history()
    return jsonify({'success': True})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Patch Agent Web Interface Starting...")
    print("="*60)
    print(f"\n📁 Target Directory: {TARGET_DIR}")
    print(f"\n🌐 Access the interface at:")
    print(f"   - Local:   http://localhost:5001")
    print(f"   - Network: http://<your-ip>:5001")
    print(f"\n💡 To find your IP address:")
    print(f"   - Windows: ipconfig")
    print(f"   - Linux/Mac: ifconfig or ip addr")
    print(f"\n🛑 Press Ctrl+C to stop the server\n")
    print("="*60 + "\n")
    
    # Run on all interfaces (0.0.0.0) to allow network access
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
