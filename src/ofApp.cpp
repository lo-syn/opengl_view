#include "ofApp.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>

namespace {
constexpr int oscPort = 8001;
}
namespace fs = std::filesystem;

//--------------------------------------------------------------
void ofApp::setup() {
	if (!oscReceiver.setup(oscPort)) {
		ofLogError("ofApp::setup") << "Failed to listen for OSC on port " << oscPort;
	}

	// Create and allocate FBO layers, 3 layers
	layerA.allocate(ofGetWidth(), ofGetHeight(), GL_RGBA);
	layerB.allocate(ofGetWidth(), ofGetHeight(), GL_RGBA);
	layerC.allocate(ofGetWidth(), ofGetHeight(), GL_RGBA);
}

//--------------------------------------------------------------
bool ofApp::loadShader(const std::string & fragPath) {
	const fs::path path(fragPath);
	if (!path.is_absolute()) {
		ofLogError("ofApp::loadShader") << "Expected an absolute path to a shader .frag file: " << fragPath;
		return false;
	}

	std::ifstream file(path);
	if (!file.is_open()) {
		ofLogError("ofApp::loadShader") << "Failed to open shader: " << path.string();
		return false;
	}

	std::stringstream buffer;
	buffer << file.rdbuf();
	if (file.bad()) {
		ofLogError("ofApp::loadShader") << "Failed to read shader: " << path.string();
		return false;
	}

	ofShader candidate;
	if (!candidate.setupShaderFromSource(GL_FRAGMENT_SHADER, buffer.str(), path.parent_path())) {
		ofLogError("ofApp::loadShader") << "Failed to compile shader: " << path.string();
		return false;
	}
	if (ofIsGLProgrammableRenderer()) {
		candidate.bindDefaults();
	}
	if (!candidate.linkProgram()) {
		ofLogError("ofApp::loadShader") << "Failed to link shader: " << path.string();
		return false;
	}

	auto & state = shaders[selectedFb];
	state.shader = std::move(candidate);
	state.loaded = true;
	state.name = path.string();
	ofLogNotice("ofApp::loadShader") << "Loaded shader " << path.string() << " on fb" << selectedFb;
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
				shaders[selectedFb].loaded = false;
				shaders[selectedFb].name = "reset";
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
}

//--------------------------------------------------------------
void ofApp::draw() {
	ofFbo * layers[] = { &layerA, &layerB, &layerC };
	ofPushStyle();
	ofDisableAlphaBlending();
	for (size_t i = 0; i < shaders.size(); ++i) {
		auto & layer = *layers[i];
		auto & state = shaders[i];

		layer.begin();
		ofClear(0, 0, 0, 0);
		if (state.loaded) {
			ofSetColor(255);
			state.shader.begin();
			state.shader.setUniform2f("u_resolution", layer.getWidth(), layer.getHeight());
			state.shader.setUniform2f("resolution", layer.getWidth(), layer.getHeight());
			state.shader.setUniform1f("u_time", ofGetElapsedTimef());
			state.shader.setUniform1f("u_x0", shaderX0);
			state.shader.setUniform1f("u_x1", shaderX1);
			state.shader.setUniform1f("u_x2", shaderX2);
			state.shader.setUniform1f("u_x3", shaderX3);
			ofDrawRectangle(0, 0, layer.getWidth(), layer.getHeight());
			state.shader.end();
		}
		layer.end();
	}

	ofBackground(0);
	ofEnableAlphaBlending();
	ofSetColor(255);
	for (auto * layer : layers) {
		layer->draw(0, 0);
	}
	ofPopStyle();
}

//--------------------------------------------------------------
void ofApp::keyPressed(int key) {
}

//--------------------------------------------------------------
void ofApp::keyReleased(int key) {
}

//--------------------------------------------------------------
void ofApp::mouseMoved(int x, int y) {
}

//--------------------------------------------------------------
void ofApp::mouseDragged(int x, int y, int button) {
}

//--------------------------------------------------------------
void ofApp::mousePressed(int x, int y, int button) {
}

//--------------------------------------------------------------
void ofApp::mouseReleased(int x, int y, int button) {
}

//--------------------------------------------------------------
void ofApp::mouseEntered(int x, int y) {
}

//--------------------------------------------------------------
void ofApp::mouseExited(int x, int y) {
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
void ofApp::gotMessage(ofMessage msg) {
}

//--------------------------------------------------------------
void ofApp::dragEvent(ofDragInfo dragInfo) {
}
