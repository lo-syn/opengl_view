#include "ofApp.h"

#include <cmath>
#include <filesystem>
#include <string>

namespace {
constexpr int oscPort = 8001;
}
namespace fs = std::filesystem;

//--------------------------------------------------------------
void ofApp::setup() {
	if (!oscReceiver.setup(oscPort)) {
		ofLogError("ofApp::setup") << "Failed to listen for OSC on port " << oscPort;
	}

	std::cout << "Listening for OSC messages on port " << oscPort << std::endl;

	layerA.allocate(1280, 720, GL_RGBA);
	layerB.allocate(1280, 720, GL_RGBA);
	layerC.allocate(1280, 720, GL_RGBA);
}

//--------------------------------------------------------------
bool ofApp::loadShader(const std::string & fragPath) {
	const fs::path path(fragPath);
	if (!path.is_absolute()) {
		ofLogError("ofApp::loadShader") << "Expected an absolute path to a shader .frag/.fs file: " << fragPath;
		return false;
	}
	if (!fs::exists(path)) {
		ofLogError("ofApp::loadShader") << "Shader file does not exist: " << path.string();
		return false;
	}

	ofFbo * layers[] = { &layerA, &layerB, &layerC };
	ofxISFScene * scenes[] = { &sceneA, &sceneB, &sceneC };
	if (selectedFb < 0 || selectedFb >= 3) {
		return false;
	}

	int w = static_cast<int>(layers[selectedFb]->getWidth());
	int h = static_cast<int>(layers[selectedFb]->getHeight());

	scenes[selectedFb]->setup(path.string(), w, h);
	sceneLoaded[selectedFb] = true;
	ofLogNotice("ofApp::loadShader") << "Loaded ISF shader " << path.string() << " on fb" << selectedFb;
	return true;
}

//--------------------------------------------------------------
void ofApp::update() {
	ofxISFScene * scenes[] = { &sceneA, &sceneB, &sceneC };

	while (oscReceiver.hasWaitingMessages()) {
		ofxOscMessage message;
		if (!oscReceiver.getNextMessage(message)) {
			continue;
		}

		const auto address = message.getAddress();

		// 1. Select active framebuffer layer
		if (address == "/fb0") {
			selectedFb = 0;
			continue;
		}
		if (address == "/fb1") {
			selectedFb = 1;
			continue;
		}
		if (address == "/fb2") {
			selectedFb = 2;
			continue;
		}

		// 2. Load or reset shader on the selected layer
		if (address == "/shader") {
			if (message.getNumArgs() != 1 || message.getArgType(0) != OFXOSC_TYPE_STRING) {
				ofLogWarning("ofApp::update") << "Expected one string argument for /shader";
				continue;
			}
			if (message.getArgAsString(0) == "reset") {
				sceneLoaded[selectedFb] = false;
				ofLogNotice("ofApp::update") << "Reset shader on fb" << selectedFb;
				continue;
			}
			loadShader(message.getArgAsString(0));
			continue;
		}

		// 3. Parse target layer and ISF parameter name from the OSC address
		int targetFb = selectedFb;
		std::string paramName;

		if (address.rfind("/fb0/", 0) == 0) {
			targetFb = 0;
			paramName = address.substr(5);
		} else if (address.rfind("/fb1/", 0) == 0) {
			targetFb = 1;
			paramName = address.substr(5);
		} else if (address.rfind("/fb2/", 0) == 0) {
			targetFb = 2;
			paramName = address.substr(5);
		} else if (address.size() > 1 && address[0] == '/') {
			paramName = address.substr(1);
		} else {
			continue;
		}

		if (paramName.empty() || targetFb < 0 || targetFb >= 3 || !sceneLoaded[targetFb]) {
			continue;
		}

		auto * targetScene = scenes[targetFb];
		const int numArgs = message.getNumArgs();

		// 4. Pass the incoming OSC argument(s) directly to the matching ISF input
		if (numArgs == 1) {
			const auto type = message.getArgType(0);
			if (type == OFXOSC_TYPE_FLOAT) {
				const float val = message.getArgAsFloat(0);
				if (std::isfinite(val)) {
					targetScene->setInput(paramName, val);
				}
			} else if (type == OFXOSC_TYPE_INT32) {
				const int32_t val = message.getArgAsInt32(0);
				targetScene->setInput(paramName, static_cast<long>(val));
				targetScene->setInput(paramName, static_cast<float>(val));
			} else if (type == OFXOSC_TYPE_TRUE || type == OFXOSC_TYPE_FALSE) {
				targetScene->setInput(paramName, message.getArgAsBool(0));
			}
		} else if (numArgs == 2 && message.getArgType(0) == OFXOSC_TYPE_FLOAT && message.getArgType(1) == OFXOSC_TYPE_FLOAT) {
			targetScene->setInput(paramName, ofVec2f(message.getArgAsFloat(0), message.getArgAsFloat(1)));
		} else if (numArgs == 4 && message.getArgType(0) == OFXOSC_TYPE_FLOAT) {
			targetScene->setInput(paramName, ofFloatColor(message.getArgAsFloat(0), message.getArgAsFloat(1), message.getArgAsFloat(2), message.getArgAsFloat(3)));
		}
	}
}

//--------------------------------------------------------------
void ofApp::draw() {
	ofFbo * layers[] = { &layerA, &layerB, &layerC };
	ofxISFScene * scenes[] = { &sceneA, &sceneB, &sceneC };

	// 1. Render each ISF scene to its own internal texture FIRST
	for (size_t i = 0; i < 3; ++i) {
		if (sceneLoaded[i]) {
			scenes[i]->update();
		}
	}

	// 2. Draw each rendered scene into its corresponding ofFbo
	ofPushStyle();
	ofDisableAlphaBlending();
	for (size_t i = 0; i < 3; ++i) {
		layers[i]->begin();
		ofClear(0, 0, 0, 0);
		if (sceneLoaded[i]) {
			ofSetColor(255);
			scenes[i]->draw(0, 0);
		}
		layers[i]->end();
	}

	// 3. Composite the three FBO layers to the screen
	ofBackground(0);
	ofEnableAlphaBlending();
	ofSetColor(255);
	for (auto * layer : layers) {
		layer->draw(0, 0);
	}
	ofPopStyle();
}

//--------------------------------------------------------------
void ofApp::windowResized(int w, int h) {
	if (w > 0 && h > 0) {
		layerA.allocate(w, h, GL_RGBA);
		layerB.allocate(w, h, GL_RGBA);
		layerC.allocate(w, h, GL_RGBA);
	}
}

//--------------------------------------------------------------
void ofApp::keyPressed(int key) { }
void ofApp::keyReleased(int key) { }
void ofApp::mouseMoved(int x, int y) { }
void ofApp::mouseDragged(int x, int y, int button) { }
void ofApp::mousePressed(int x, int y, int button) { }
void ofApp::mouseReleased(int x, int y, int button) { }
void ofApp::mouseEntered(int x, int y) { }
void ofApp::mouseExited(int x, int y) { }
void ofApp::gotMessage(ofMessage msg) { }
void ofApp::dragEvent(ofDragInfo dragInfo) { }
