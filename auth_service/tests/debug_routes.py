import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from auth_service.main import app

# Print all routes with their complete paths
print("All registered routes:")
for route in app.routes:
    if hasattr(route, "path"):
        print(f"- {route.path}")

# Specifically look for register endpoint
register_routes = [route for route in app.routes if "register" in getattr(route, "path", "")]
print("\nRegister routes:")
for route in register_routes:
    print(f"- {route.path} [{','.join(route.methods)}]")
