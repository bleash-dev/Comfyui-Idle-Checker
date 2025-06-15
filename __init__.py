from .nodes import IdleDetectorExtension
from .api import setup_routes

# Set the web directory for frontend files
WEB_DIRECTORY = "./js"

# Setup API routes
setup_routes()

# A dictionary that contains all nodes you want to export with their names
# IdleDetectorExtension is a background service, not a node, so we don't export it
NODE_CLASS_MAPPINGS = {
}

# A dictionary that contains the friendly/humanly readable titles for the nodes
NODE_DISPLAY_NAME_MAPPINGS = {
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
