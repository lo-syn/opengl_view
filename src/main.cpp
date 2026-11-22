#include "ofMain.h"
#include "ofApp.h"

//========================================================================
int main( ){
	// Use a borderless window so the external shader menu can remain above it.
	ofGLFWWindowSettings settings;

	settings.setSize(1920, 1080);
	settings.setPosition({0, 0});
	settings.windowMode = OF_WINDOW;
	settings.decorated = false;
	auto window = ofCreateWindow(settings);

	ofRunApp(window, std::make_shared<ofApp>());
	ofRunMainLoop();

}
