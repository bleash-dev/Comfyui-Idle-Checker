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

    @PromptServer.instance.routes.post("/idle_detector/autosave")
    async def autosave_workflow(request):
        """Endpoint to autosave a workflow."""
        request_data = await request.json()
        workflow_data = request_data.get("workflow")
        filename = request_data.get("filename")

        if not workflow_data or not filename:
            return web.json_response({"status": "error", "message": "Missing workflow data or filename"}, status=400)

        filepath = idle_detector.save_workflow_data(workflow_data, filename)
        if filepath:
            return web.json_response({"status": "success", "message": f"Workflow saved to {filepath}"})
        else:
            return web.json_response({"status": "error", "message": "Failed to save workflow"}, status=500)
