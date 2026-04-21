import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            
            if not post_data:
                self.send_response(400)
                self.end_headers()
                return

            data = json.loads(post_data)

            # PostHog webhook payload structure contains the properties
            properties = data.get('event', {}).get('properties', {})
            if not properties:
                properties = data.get('properties', {})
                
            error_message = properties.get('error_message', 'Unknown Error')
            traceback = properties.get('traceback', 'No traceback')
            file_name = properties.get('file_name', 'fake_app.py')

            github_token = os.environ.get("GITHUB_PAT")
            # The repository in format "username/repo"
            repo_owner_and_name = os.environ.get("GITHUB_REPO", "armaanamatya/geometask") 
            
            url = f"https://api.github.com/repos/{repo_owner_and_name}/dispatches"
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"token {github_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "event_type": "posthog_error",
                "client_payload": {
                    "error_message": error_message,
                    "traceback": traceback,
                    "file_name": file_name
                }
            }
            
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            
            with urllib.request.urlopen(req) as response:
                result = response.read()
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "dispatched": True}).encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
