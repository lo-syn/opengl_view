#pragma once

#include "ofMain.h"
#include "ofxOsc.h"
#include <nlohmann/json.hpp>

class ofApp : public ofBaseApp
{
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

	ofShader shader;
	bool shaderLoaded = false;
	ofxOscReceiver oscReceiver;
	float shaderX0 = 0.1f;
	float shaderX1 = 0.1f;
	float shaderX2 = 0.1f;
	float shaderX3 = 0.1f;

private:
	bool loadShader(const std::string &name);
	bool LoadShaderPack(const std::string &packFolderName);
	std::string shaderDirectory;
	std::string currentShaderName = "blob";
	std::string shaderPackRoot;
	nlohmann::json shaderPrograms = nlohmann::json::object();
};
