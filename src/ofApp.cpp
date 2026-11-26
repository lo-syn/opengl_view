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
	while (oscReceiver.hasWaitingMessages()) {
		ofxOscMessage message;
		if (!oscReceiver.getNextMessage(message)) {
			continue;
		}
		const auto address = message.getAddress();

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

		float * shaderValue = nullptr;
		if (address == "/u_x0") {
			shaderValue = &shaderX0;
		} else if (address == "/u_x1") {
			shaderValue = &shaderX1;
		} else if (address == "/u_x2") {
			shaderValue = &shaderX2;
		} else if (address == "/u_x3") {
			shaderValue = &shaderX3;
		} else {
			continue;
		}

		if (message.getNumArgs() != 1) {
			ofLogWarning("ofApp::update") << "Expected one numeric argument for " << address;
			continue;
		}

		const auto type = message.getArgType(0);
		if (type != OFXOSC_TYPE_FLOAT && type != OFXOSC_TYPE_INT32) {
			ofLogWarning("ofApp::update") << "Expected a float or integer argument for " << address;
			continue;
		}

		const float value = message.getArgAsFloat(0);
		if (!std::isfinite(value)) {
			ofLogWarning("ofApp::update") << "Ignoring non-finite value for " << address;
			continue;
		}

		*shaderValue = value;
	}

	// Push shared uniforms into each loaded ISF scene
	ofxISFScene * scenes[] = { &sceneA, &sceneB, &sceneC };
	for (size_t i = 0; i < 3; ++i) {
		if (!sceneLoaded[i]) {
			continue;
		}
		scenes[i]->setInput("u_x0", shaderX0);
		scenes[i]->setInput("u_x1", shaderX1);
		scenes[i]->setInput("u_x2", shaderX2);
		scenes[i]->setInput("u_x3", shaderX3);
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
