#pragma once

#include "ofMain.h"
#include "ofxOsc.h"
#include <array>
#include <string>
#include "ofxISFScene.h"


class ofApp : public ofBaseApp {
public:
	void setup();
	void update();
	void draw();
	ofFbo layerA;
	ofFbo layerB;
	ofFbo layerC;

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

	ofxOscReceiver oscReceiver;
	ofxISFScene sceneA;
	ofxISFScene sceneB;
	ofxISFScene sceneC;
	std::array<bool, 3> sceneLoaded = { false, false, false };

	struct ParamInfo {
		std::string name;
		VVISF::ISFValType type;
		float minVal = 0.0f;
		float maxVal = 1.0f;
	};
	std::array<std::vector<ParamInfo>, 3> sceneParams;
	float shaderX0 = 0.1f;
	float shaderX1 = 0.1f;
	float shaderX2 = 0.1f;
	float shaderX3 = 0.1f;
	int selectedFb = 0;

	bool loadShader(const std::string & fragPath);
};
