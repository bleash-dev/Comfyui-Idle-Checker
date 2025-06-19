import { app } from "../../../scripts/app.js";

class IdleDetectorExtension {
    constructor() {
        this.isActive = true;
        this.lastActivityTime = Date.now();
        this.activityTimeout = null;
        this.inactivityThreshold = 60000; // 1 minute of no activity before considering idle
        
        this.autoSaveTimeout = null;
        this.autoSaveThreshold = 5000; // 5 seconds for auto-save

        this.setupEventListeners();
        this.setupVisibilityAPI();
        this.setupActivityTracking();
        
        // Set initial status to active
        this.setStatus('active');
        this.onUserActivity(); // Start timers to enable auto-saving from the start
    }

    setupFilenameTracking() {
        // When a workflow is loaded from the server list, ComfyUI doesn't set app.graph_filename.
        // We patch the loader to ensure the filename is tracked for autosaving.
        const originalLoader = app.loadWorkflowFromServer;
        if (!originalLoader.isPatchedByIdleDetector) {
            app.loadWorkflowFromServer = async function (filename) {
                app.graph_filename = filename;
                console.log("Idle Detector: 📁 Server-side workflow loaded:", filename);
                const result = await originalLoader.call(app, filename);
                return result;
            };
            app.loadWorkflowFromServer.isPatchedByIdleDetector = true;
        }

        // When the graph is cleared (e.g., new workflow), we should reset the filename.
        const originalClear = app.graph.clear;
        if (!originalClear.isPatchedByIdleDetector) {
            app.graph.clear = function () {
                app.graph_filename = null;
                console.log("Idle Detector: 📋 Graph cleared, filename reset for autosave.");
                originalClear.apply(app.graph, arguments);
            };
            app.graph.clear.isPatchedByIdleDetector = true;
        }

        // To handle file uploads via the "Load" button or drag-and-drop, we patch app.handleFile.
        // This ensures we capture the filename for any user-uploaded workflow.
        const originalHandleFile = app.handleFile;
        if (!originalHandleFile.isPatchedByIdleDetector) {
            app.handleFile = async function (file) {
                const result = await originalHandleFile.apply(app, arguments);
                // After the original function runs, if a workflow was loaded,
                // app.graph_filename will be set. We log this to confirm our tracking works.
                if (file?.name?.endsWith(".json") && app.graph_filename === file.name) {
                    console.log("Idle Detector: 📂 Workflow file upload tracked:", file.name);
                }
                return result;
            };
            app.handleFile.isPatchedByIdleDetector = true;
        }
    }

    setupEventListeners() {
        // Track various user interactions
        const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
        
        events.forEach(event => {
            document.addEventListener(event, () => {
                this.onUserActivity();
            }, true);
        });
    }

    setupVisibilityAPI() {
        // Handle page visibility changes (more reliable for app switching)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Page hidden (app switch or tab change) - setting status to idle');
                this.setStatus('idle');
            } else {
                console.log('Page visible - setting status to active');
                this.setStatus('active');
                this.onUserActivity();
            }
        });

        // Handle page unload
        window.addEventListener('beforeunload', () => {
            this.setStatus('idle');
        });

        // Handle window focus/blur (fallback for older browsers)
        window.addEventListener('focus', () => {
            if (!this.isActive) {
                console.log('Window focused - setting status to active');
                this.setStatus('active');
                this.onUserActivity();
            }
        });

        window.addEventListener('blur', () => {
            console.log('Window blurred - setting status to idle');
            this.setStatus('idle');
        });

        // Additional detection for macOS app switching
        // Use a combination of document.hasFocus() polling and visibility API
        this.setupFocusPolling();
    }

    setupFocusPolling() {
        // Poll document.hasFocus() to detect app switches on macOS
        setInterval(() => {
            const hasFocus = document.hasFocus();
            const isVisible = !document.hidden;
            
            // If document doesn't have focus or is hidden, consider it idle
            if (!hasFocus || !isVisible) {
                if (this.isActive) {
                    console.log('Focus polling detected app switch - setting status to idle');
                    this.setStatus('idle');
                }
            } else if (!this.isActive && hasFocus && isVisible) {
                console.log('Focus polling detected app return - setting status to active');
                this.setStatus('active');
                this.onUserActivity();
            }
        }, 1000); // Check every second
    }

    setupActivityTracking() {
        // Monitor ComfyUI specific activities
        const originalQueuePrompt = app.queuePrompt;
        app.queuePrompt = function(...args) {
            this.onUserActivity();
            return originalQueuePrompt.apply(app, args);
        }.bind(this);

        // Monitor graph changes
        if (app.graph && app.graph.change) {
            const originalChange = app.graph.change;
            app.graph.change = function(...args) {
                this.onUserActivity();
                return originalChange.apply(app.graph, args);
            }.bind(this);
        }
    }

    onUserActivity() {
        this.lastActivityTime = Date.now();
        
        if (!this.isActive && !document.hidden) {
            console.log('User activity detected - setting status to active');
            this.setStatus('active');
        }

        // Clear any existing idle timer
        if (this.activityTimeout) {
            clearTimeout(this.activityTimeout);
        }

        // Start new idle timer
        this.startIdleTimer();

        // Clear and restart auto-save timer
        if (this.autoSaveTimeout) {
            clearTimeout(this.autoSaveTimeout);
        }
        this.startAutoSaveTimer();
    }

    startIdleTimer() {
        if (this.activityTimeout) {
            clearTimeout(this.activityTimeout);
        }

        this.activityTimeout = setTimeout(() => {
            // Only set to idle if the page is still visible and has focus
            // If page is hidden, it should already be idle from visibility API
            if (!document.hidden && document.hasFocus()) {
                console.log('No activity for', this.inactivityThreshold / 1000, 'seconds - setting status to idle');
                this.setStatus('idle');
            }
        }, this.inactivityThreshold);
    }

    startAutoSaveTimer() {
        this.autoSaveTimeout = setTimeout(() => {
            this.autoSaveWorkflow();
        }, this.autoSaveThreshold);
    }

    async autoSaveWorkflow() {
        console.log("Auto-saving workflow due to inactivity...");
        try {
            const filename = app.graph_filename || "autosave.json";
            const workflow = app.graph.serialize();
            const payload = {
                workflow: workflow,
                filename: filename,
            };

            const response = await fetch("/idle_detector/autosave", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(payload),
            });

            if (response.ok) {
                const data = await response.json();
                console.log("Workflow auto-saved successfully:", data.message);
            } else {
                console.error("Failed to auto-save workflow:", response.statusText);
            }
        } catch (error) {
            console.error("Error auto-saving workflow:", error);
        }
    }

    async setStatus(status) {
        if (this.isActive === (status === 'active')) {
            return; // No change needed
        }

        this.isActive = (status === 'active');

        try {
            const endpoint = status === 'active' ? 
                '/idle_detector/set_active' : 
                '/idle_detector/set_idle';
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`Status set to ${status}:`, data);
            } else {
                console.error('Failed to set status:', response.statusText);
            }
        } catch (error) {
            console.error('Error setting status:', error);
        }
    }

    async getStatus() {
        try {
            const response = await fetch('/idle_detector/status');
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Error getting status:', error);
        }
        return null;
    }
}

// Register the extension with ComfyUI
app.registerExtension({
    name: "comfyui.idle.detector",
    async setup() {
        const idleDetector = new IdleDetectorExtension();
        idleDetector.setupFilenameTracking();
    }
});
