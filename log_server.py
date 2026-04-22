import http.server
import socketserver
import sys
import os

PORT = 5000
LOG_FILE = "access.log"

# Ensure log file exists
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, 'w') as f:
        f.write(f"# Access Logs for server on port {PORT}\n")

class LoggingHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Format the log string manually to match common access log format
        log_entry = "%s - - [%s] %s\n" % (
            self.client_address[0],
            self.log_date_time_string(),
            format % args
        )
        
        # Write to file
        try:
            with open(LOG_FILE, "a") as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error writing to log file: {e}")

        # Also print to stderr so we can see it in console if needed
        sys.stderr.write(log_entry)

Handler = LoggingHandler

# Allow reuse of address to avoid "Address already in use" errors on quick restarts
socketserver.TCPServer.allow_reuse_address = True

print(f"[*] Starting Log Server on port {PORT}")
print(f"[*] Logs will be written to: {os.path.abspath(LOG_FILE)}")

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping server...")
        httpd.server_close()
