import os
import time
import traceback
from posthog import Posthog
from dotenv import load_dotenv

load_dotenv()

# These will be set later in your environment
POSTHOG_API_KEY = os.environ.get('POSTHOG_API_KEY', 'dummy_key')
POSTHOG_HOST = os.environ.get('POSTHOG_HOST', 'https://app.posthog.com')

posthog = Posthog(project_api_key=POSTHOG_API_KEY, host=POSTHOG_HOST)

def run_browser_simulation():
    print("Starting browser simulation tasks...")
    # -------------------------------------------------------------
    # INTENTIONAL BUG: An error that is "super easy to fix"
    # We are calling a method on a NoneType object.
    # The agent should easily recognize that my_string needs a value
    # or that the logic is flawed.
    # -------------------------------------------------------------
    my_string = None
    print(my_string.upper())

if __name__ == "__main__":
    while True:
        try:
            run_browser_simulation()
            print("Simulation succeeded! Waiting before next run.")
            time.sleep(10)
        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()
            print(f"Error caught: {error_msg}")
            
            # The name of the file where the error occurred
            file_name = "fake_app.py"
            
            # Push the error to PostHog
            posthog.capture(
                'distinct_id_server', # Dummy ID for the server/device
                event='browser_error', 
                properties={
                    'error_message': error_msg,
                    'traceback': tb,
                    'file_name': file_name
                }
            )
            print("Error telemetry sent to Posthog. Waiting before retrying...")
            time.sleep(10)
