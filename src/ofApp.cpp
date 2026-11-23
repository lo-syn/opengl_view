#include "ofApp.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <nlohmann/json.hpp>
#include <sstream>
#include <string>
#include <utility>

namespace {
constexpr int oscPort = 8001;
void LoadShaderPack(const std::string & packFolderName);
}
namespace fs = std::filesystem;

//--------------------------------------------------------------
void ofApp::setup() {

	LoadShaderPack("ShaderPack1");

	shaderDirectory = ofIsGLProgrammableRenderer()
		? "shadersGL3"
		: "shadersGL2";

	if (!oscReceiver.setup(oscPort)) {
		ofLogError("ofApp::setup") << "Failed to listen for OSC on port " << oscPort;
	}
}

//--------------------------------------------------------------
std::string LoadShaderWithDefines(const fs::path & filepath, const std::vector<std::string> & defines) {
	std::ifstream file(filepath);
	if (!file.is_open()) {
		throw std::runtime_error("Failed to open shader: " + filepath.string());
	}

	std::stringstream buffer;
	buffer << file.rdbuf();
	std::string source = buffer.str();

	// Inject #define macros right after the #version line
	if (!defines.empty()) {
		size_t versionPos = source.find("#version");
		size_t lineEnd = (versionPos != std::string::npos) ? source.find('\n', versionPos) + 1 : 0;

		std::string defineBlock;
		for (const auto & def : defines) {
			defineBlock += "#define " + def + "\n";
		}
		source.insert(lineEnd, defineBlock);
	}

	return source;
}

// Loads a shader pack from the specified folder name, reading its manifest and preparing shader programs.
//--------------------------------------------------------------
namespace {
void LoadShaderPack(const std::string & packFolderName) {
	// Resolves to "<current_working_directory>/bin/data/<packFolderName>"
	fs::path packRoot = fs::current_path() / "data";
	//packFolderName
	fs::path manifestPath = packRoot / "manifest.json";

	if (!fs::exists(manifestPath)) {
		std::cerr << "Manifest not found at: " << manifestPath << "\n";
		return;
	}

	std::ifstream file(manifestPath);
	nlohmann::json manifest = nlohmann::json::parse(file);
	ofLogNotice("manifest") << manifest.dump(2);

	for (auto & [progName, config] : manifest["programs"].items()) {
		fs::path vertPath = packRoot / config["vertex"].get<std::string>();
		fs::path fragPath = packRoot / config["fragment"].get<std::string>();

		std::vector<std::string> defines;
		if (config.contains("defines")) {
			defines = config["defines"].get<std::vector<std::string>>();
		}

		std::string vertCode = LoadShaderWithDefines(vertPath, defines);
		std::string fragCode = LoadShaderWithDefines(fragPath, defines);

		// Compile vertCode & fragCode and link into GPU shader program under `progName`
		std::cout << "Loaded shader program: " << progName << "\n";
	}
}
}

//--------------------------------------------------------------
bool ofApp::loadShader(const std::string & name) {
	std::string fragmentShaderName;
	if (name == "blob") {
		fragmentShaderName = "blob.frag";
	} else if (name == "shader") {
		fragmentShaderName = "shader.frag";
	} else {
		ofLogWarning("ofApp::loadShader") << "Unknown shader: " << name;
		return false;
	}

	const auto vertexShaderPath = ofToDataPath(shaderDirectory + "/shader.vert");
	const auto fragmentShaderPath = ofToDataPath(shaderDirectory + "/" + fragmentShaderName);
	ofShader candidate;
	if (!candidate.load(vertexShaderPath, fragmentShaderPath)) {
		ofLogError("ofApp::loadShader") << "Failed to load " << fragmentShaderName;
		return false;
	}

	shader = std::move(candidate);
	shaderLoaded = true;
	currentShaderName = name;
	ofLogNotice("ofApp::loadShader") << "Loaded " << fragmentShaderName;
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
		if (address == "/shader") {
			if (message.getNumArgs() != 1 || message.getArgType(0) != OFXOSC_TYPE_STRING) {
				ofLogWarning("ofApp::update") << "Expected one string argument for /shader";
				continue;
			}
			if (message.getArgAsString(0) == "reset") {
				shaderLoaded = false;
				currentShaderName = "reset";
				ofLogNotice("ofApp::update") << "Reset shader";
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
	ofBackground(0);
	if (!shaderLoaded) {
		return;
	}

	ofSetColor(255);
	const auto viewport = ofGetNativeViewport();
	shader.begin();
	shader.setUniform2f("u_resolution", viewport.width, viewport.height);
	shader.setUniform2f("resolution", viewport.width, viewport.height);
	shader.setUniform1f("u_time", ofGetElapsedTimef());
	shader.setUniform1f("u_x0", shaderX0);
	shader.setUniform1f("u_x1", shaderX1);
	shader.setUniform1f("u_x2", shaderX2);
	shader.setUniform1f("u_x3", shaderX3);
	ofDrawRectangle(0, 0, ofGetWidth(), ofGetHeight());
	shader.end();
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
}

//--------------------------------------------------------------
void ofApp::gotMessage(ofMessage msg) {
}

//--------------------------------------------------------------
void ofApp::dragEvent(ofDragInfo dragInfo) {
}