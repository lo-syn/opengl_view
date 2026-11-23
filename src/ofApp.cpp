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
}

//--------------------------------------------------------------
std::string LoadShaderWithDefines(const fs::path & filepath, const std::vector<std::string> & defines) {
	std::ifstream file(filepath);
	if (!file.is_open()) {
		throw std::runtime_error("Failed to open shader: " + filepath.string());
	}

	std::stringstream buffer;
	buffer << file.rdbuf();
	if (file.bad()) {
		throw std::runtime_error("Failed to read shader: " + filepath.string());
	}
	std::string source = buffer.str();

	// Inject #define macros right after the #version line
	if (!defines.empty()) {
		size_t versionPos = source.find("#version");
		size_t lineEnd = 0;
		if (versionPos != std::string::npos) {
			lineEnd = source.find('\n', versionPos);
			if (lineEnd == std::string::npos) {
				source += '\n';
				lineEnd = source.size();
			} else {
				++lineEnd;
			}
		}

		std::string defineBlock;
		for (const auto & def : defines) {
			defineBlock += "#define " + def + "\n";
		}
		source.insert(lineEnd, defineBlock);
	}

	return source;
}

// Loads a shader pack manifest; programs are compiled when selected.
//--------------------------------------------------------------
bool ofApp::LoadShaderPack(const std::string & packFolderName) {
	const fs::path packName(packFolderName);
	if (packFolderName.empty() || packName != packName.filename()
		|| packName == "." || packName == "..") {
		ofLogError("ofApp::LoadShaderPack") << "Invalid shader bank name: " << packFolderName;
		return false;
	}

	const fs::path dataRoot = ofToDataPath("", true);
	fs::path packRoot = dataRoot / "Shaders";
	fs::path manifestPath = packRoot / "manifest.json";
	bool rootManifest = false;

	std::error_code error;
	const bool manifestExists = fs::exists(manifestPath, error);
	if (error) {
		ofLogError("ofApp::LoadShaderPack") << "Cannot access manifest " << manifestPath << ": " << error.message();
		return false;
	}
	if (!manifestExists) {
		packRoot = dataRoot;
		manifestPath = dataRoot / "manifest.json";
		rootManifest = true;
	}

	std::ifstream file(manifestPath);
	if (!file.is_open()) {
		ofLogError("ofApp::LoadShaderPack") << "Manifest not found or unreadable for bank "
											<< packFolderName << ": " << manifestPath;
		return false;
	}
	try {
		nlohmann::json manifest = nlohmann::json::parse(file);
		if (!manifest.is_object() || !manifest.contains("pack_names") || !manifest["pack_names"].is_object()) {
			ofLogError("ofApp::LoadShaderPack") << "Invalid pack_names object in " << manifestPath;
			return false;
		}
		const auto pack = manifest["pack_names"].find(packFolderName);
		if (pack == manifest["pack_names"].end() || !pack->is_object()) {
			ofLogError("ofApp::LoadShaderPack") << "Manifest not found for shader bank: " << packFolderName;
			return false;
		}
		shaderPrograms = std::move(*pack);
		shaderPackRoot = rootManifest ? packRoot.string() : (packRoot / packFolderName).string();
		ofLogNotice("ofApp::LoadShaderPack") << "Loaded shader bank: " << packFolderName;
		return true;
	} catch (const nlohmann::json::exception & error) {
		ofLogError("ofApp::LoadShaderPack") << "Invalid manifest " << manifestPath << ": " << error.what();
		return false;
	}
}

//--------------------------------------------------------------
bool ofApp::loadShader(const std::string & name) {
	const std::string programName = name == "blob" && !shaderPrograms.contains(name) ? "Blob" : name;
	const auto config = shaderPrograms.find(programName);
	if (config == shaderPrograms.end() && name != "shader") {
		ofLogError("ofApp::loadShader") << "Unknown shader in current bank: " << name;
		return false;
	}

	ofShader candidate;
	if (config == shaderPrograms.end()) {
		const auto vertexShaderPath = ofToDataPath(shaderDirectory + "/shader.vert");
		const auto fragmentShaderPath = ofToDataPath(shaderDirectory + "/shader.frag");
		if (!candidate.load(vertexShaderPath, fragmentShaderPath)) {
			ofLogError("ofApp::loadShader") << "Failed to load shader.frag";
			return false;
		}
	} else {
		try {
			const fs::path vertPath = fs::path(shaderPackRoot) / config->at("vertex").get<std::string>();
			const fs::path fragPath = fs::path(shaderPackRoot) / config->at("fragment").get<std::string>();
			std::vector<std::string> defines;
			if (config->contains("defines")) {
				defines = config->at("defines").get<std::vector<std::string>>();
			}
			const std::string vertCode = LoadShaderWithDefines(vertPath, defines);
			const std::string fragCode = LoadShaderWithDefines(fragPath, defines);
			if (!candidate.setupShaderFromSource(GL_VERTEX_SHADER, vertCode, vertPath.parent_path())
				|| !candidate.setupShaderFromSource(GL_FRAGMENT_SHADER, fragCode, fragPath.parent_path())) {
				ofLogError("ofApp::loadShader") << "Failed to compile shader program: " << programName;
				return false;
			}
			if (ofIsGLProgrammableRenderer()) {
				candidate.bindDefaults();
			}
			if (!candidate.linkProgram()) {
				ofLogError("ofApp::loadShader") << "Failed to link shader program: " << programName;
				return false;
			}
		} catch (const nlohmann::json::exception & error) {
			ofLogError("ofApp::loadShader") << "Invalid manifest entry for " << programName << ": " << error.what();
			return false;
		} catch (const std::runtime_error & error) {
			ofLogError("ofApp::loadShader") << error.what();
			return false;
		}
	}

	shader = std::move(candidate);
	shaderLoaded = true;
	currentShaderName = programName;
	ofLogNotice("ofApp::loadShader") << "Loaded shader program: " << programName;
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
		if (address == "/shader_pack") {
			if (message.getNumArgs() != 1 || message.getArgType(0) != OFXOSC_TYPE_STRING) {
				ofLogWarning("ofApp::update") << "Expected one string argument for /shader_pack";
				continue;
			}
			LoadShaderPack(message.getArgAsString(0));
			continue;
		}
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