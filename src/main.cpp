#include "ofApp.h"
#include "ofMain.h"

//========================================================================
int main() {
	// Use a borderless window so the external shader menu can remain above it.
	ofGLFWWindowSettings settings;

	settings.setSize(1280, 720);
	settings.setPosition({ 0, 0 });
	settings.windowMode = OF_WINDOW;
	settings.decorated = false;
	auto window = ofCreateWindow(settings);
	if (!window || !window->getWindowContext() || !glGetString(GL_VERSION)) {
		ofLogError("main") << "Failed to create an OpenGL window and context";
		return 1;
	}
#ifndef TARGET_OPENGLES
	if (!glCreateProgram || !glCreateShader) {
		ofLogError("main") << "OpenGL shader functions are unavailable";
		return 1;
	}
#endif

	ofRunApp(window, std::make_shared<ofApp>());
	ofRunMainLoop();
}
