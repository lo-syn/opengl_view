#pragma once

#include "ofMain.h"
#include "ofxOsc.h"

class ofApp : public ofBaseApp{
	public:
		void setup();
		void update();
		void draw();
		
		void keyPressed(int key);
		void keyReleased(int key);
		void mouseMoved(int x, int y);
		void mouseDragged(int x, int y, int button);
		void mousePressed(int x, int y, int button);
		void mouseReleased(int x, int y, int button);
		void mouseEntered(int x, int y);
		void mouseExited(int x, int y);
		void windowResized(int w, int h);
		void dragEvent(ofDragInfo dragInfo);
		void gotMessage(ofMessage msg);

		ofShader shader;
		bool shaderLoaded = false;
		ofxOscReceiver oscReceiver;
		float shaderX0 = 0.1f;
		float shaderX1 = 0.5f;
		float shaderX2 = 0.5f;

	private:
		bool loadShader(const std::string& name);
		std::string shaderDirectory;
		std::string currentShaderName = "blob";
};
