import sys
import logging
import colorama
from colorama import Fore, Style
from patch_agent.agent import PatchAgent

# Initialize colorama for Windows support
colorama.init()

# Configure logging to be less verbose for the chat interface, 
# or redirect it to a file so it doesn't clutter the chat.
# For this demo, we'll keep it but style it differently or just let it print.
# Let's set logging to only warnings to keep chat clean, unless verbose is requested.
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("PatchAgent")
logger.setLevel(logging.INFO)

TARGET_DIR = "./vulnerable-next-js-poc-main"

def print_bot(msg):
    print(f"{Fore.CYAN}Patch Agent:{Style.RESET_ALL} {msg}")

def print_system(msg):
    print(f"{Fore.YELLOW}[System]{Style.RESET_ALL} {msg}")

def main():
    print(f"{Fore.GREEN}=========================================={Style.RESET_ALL}")
    print(f"{Fore.GREEN}       Patch Agent - Interactive Mode      {Style.RESET_ALL}")
    print(f"{Fore.GREEN}=========================================={Style.RESET_ALL}")
    print(f"Target Directory: {TARGET_DIR}")
    print("Type 'exit' or 'quit' to stop.\n")

    print_system("Initializing Agent...")
    try:
        agent = PatchAgent(TARGET_DIR)
    except Exception as e:
        print_system(f"Error initializing agent: {e}")
        return

    while True:
        try:
            user_input = input(f"{Fore.MAGENTA}You:{Style.RESET_ALL} ").strip()
        except KeyboardInterrupt:
            print("\n")
            break

        if user_input.lower() in ['exit', 'quit']:
            break
        
        if not user_input:
            continue

        print_bot("Received bug report. Analyzing...")
        
        # Run the agent
        # The agent.run command currently returns True/False
        # We might want to capture the logs or output to show progress.
        # Since the agent logs to stdout/stderr via the logging module, they will show up.
        
        print_system("--- Agent Execution Start ---")
        try:
            success = agent.run(user_input)
            print_system("--- Agent Execution End ---")
            
            if success:
                print_bot("Use checked the code and applied a fix successfully! 🛠️")
            else:
                print_bot("I attempted to fix it but encountered an error or failed validation. ❌")
        except Exception as e:
            print_system(f"Critical Error during execution: {e}")

    print_system("Goodbye!")

if __name__ == "__main__":
    main()
