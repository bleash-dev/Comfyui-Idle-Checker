from datetime import datetime
from aiohttp import web
from server import PromptServer
from .nodes import idle_detector

def setup_routes():
    """Setup API routes for idle detection"""
    
    @PromptServer.instance.routes.post("/idle_detector/set_active")
    async def set_active(request):
        idle_detector.set_active()
        return web.json_response({"status": "active", "timestamp": datetime.now().isoformat()})

    @PromptServer.instance.routes.post("/idle_detector/set_idle")
    async def set_idle(request):
        idle_detector.set_idle()
        return web.json_response({"status": "idle", "timestamp": datetime.now().isoformat()})

    @PromptServer.instance.routes.get("/idle_detector/status")
    async def get_status(request):
        status_data = idle_detector.get_status_data()
        return web.json_response(status_data)
